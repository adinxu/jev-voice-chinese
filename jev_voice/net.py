"""Minimal standard-library HTTP client with connection reuse.

Replaces httpx. Uses http.client directly so one TCP+TLS connection per host
stays warm, which keeps per-command Jev latency low without a third-party
dependency. The connection is dropped and retried once on any transport error.

Public surface mirrors the small part of httpx this project used:
    get(url, ...)                  -> Response
    post_json(url, payload, ...)   -> Response
    post_multipart(url, fields, files, ...) -> Response
"""
from __future__ import annotations

import http.client
import json as _json
import ssl
import threading
import uuid
from typing import Any
from urllib.parse import urlsplit


class HTTPError(RuntimeError):
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body[:300].decode('utf-8', 'replace')}")


class Response:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body

    @property
    def status_code(self) -> int:
        return self.status

    @property
    def content(self) -> bytes:
        return self.body

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def json(self) -> Any:
        return _json.loads(self.body.decode("utf-8"))

    def raise_for_status(self) -> "Response":
        if self.status >= 400:
            raise HTTPError(self.status, self.body)
        return self


class _Entry:
    __slots__ = ("conn", "lock")

    def __init__(self, conn: http.client.HTTPConnection) -> None:
        self.conn = conn
        self.lock = threading.Lock()


class _Pool:
    def __init__(self) -> None:
        self._pool_lock = threading.Lock()
        self._entries: dict[tuple[str, str, int], _Entry] = {}

    @staticmethod
    def _new_conn(scheme: str, host: str, port: int, timeout: float) -> http.client.HTTPConnection:
        if scheme == "https":
            return http.client.HTTPSConnection(
                host, port, timeout=timeout, context=ssl.create_default_context()
            )
        return http.client.HTTPConnection(host, port, timeout=timeout)

    def _entry(self, scheme: str, host: str, port: int, timeout: float) -> _Entry:
        key = (scheme, host, port)
        with self._pool_lock:
            entry = self._entries.get(key)
            if entry is None:
                entry = _Entry(self._new_conn(scheme, host, port, timeout))
                self._entries[key] = entry
            else:
                entry.conn.timeout = timeout
            return entry

    def request(
        self,
        method: str,
        url: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 15.0,
    ) -> Response:
        parts = urlsplit(url)
        scheme = parts.scheme or "https"
        host = parts.hostname or ""
        port = parts.port or (443 if scheme == "https" else 80)
        path = parts.path or "/"
        if parts.query:
            path = f"{path}?{parts.query}"
        headers = dict(headers or {})
        entry = self._entry(scheme, host, port, timeout)
        with entry.lock:
            for attempt in (0, 1):
                try:
                    entry.conn.request(method, path, body=body, headers=headers)
                    resp = entry.conn.getresponse()
                    data = resp.read()
                    return Response(resp.status, data)
                except Exception:
                    try:
                        entry.conn.close()
                    except Exception:
                        pass
                    entry.conn = self._new_conn(scheme, host, port, timeout)
                    if attempt == 1:
                        raise
        raise RuntimeError("unreachable")


_POOL = _Pool()


def get(url: str, *, headers: dict[str, str] | None = None, timeout: float = 5.0) -> Response:
    return _POOL.request("GET", url, headers=headers, timeout=timeout)


def post_json(
    url: str,
    payload: Any,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> Response:
    body = _json.dumps(payload).encode("utf-8")
    merged = {"Content-Type": "application/json", **(headers or {})}
    return _POOL.request("POST", url, body=body, headers=merged, timeout=timeout)


def post_multipart(
    url: str,
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> Response:
    boundary = "----jevvoice" + uuid.uuid4().hex
    buf = bytearray()
    for name, value in fields.items():
        buf += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
    for name, (filename, content, content_type) in files.items():
        buf += (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n"
        ).encode()
        buf += content + b"\r\n"
    buf += f"--{boundary}--\r\n".encode()
    merged = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(buf)),
        **(headers or {}),
    }
    return _POOL.request("POST", url, body=bytes(buf), headers=merged, timeout=timeout)
