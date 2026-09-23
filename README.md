# Jev Voice

> 中文用户请看下方 **[中文使用说明](#中文使用说明)**（完整文档见 [USAGE.zh-CN.md](USAGE.zh-CN.md)）。

Talk to your Mac. You speak, it opens apps, types, searches, scrolls, presses keys.

Everything runs locally except one ~250 ms call to **Jev** (TypeSafe's System One
model), which turns the transcript into a typed action plus typed arguments in a
single fan-out request. Jev never generates text; code produces candidate values
and Jev *selects*. Code owns execution.

```
mic ─► energy VAD ─► whisper.cpp (Metal, ~100 ms) ─► Jev (1 request, ~250 ms) ─► macOS actions ─► `say`
```

## 中文使用说明

本仓库在原版基础上新增了 **中文语音支持**，并精简了运行依赖。完整文档见 [USAGE.zh-CN.md](USAGE.zh-CN.md)。

**安装**（与原版一致）：

```sh
cp .env.example .env          # 填入 TYPESAFE_API_KEY
./scripts/setup.sh
```

**中文配置**（`.env`）：

```env
WHISPER_MODEL=/绝对路径/models/ggml-small.bin   # 多语言模型（不要用 .en 英文专用版）
WHISPER_LANG=zh
WHISPER_TRANSLATE=0                             # 中文直接交给 Jev，无需翻译
WAKE_WORDS=露娜,路那,路纳,路納,入那,luna           # 唤醒词 + 常见同音变体
FOLLOWUP_SECONDS=10                             # 喊一次后 10 秒内可连续说
UNNAMED_COMMANDS=0                              # 必须含唤醒词才发送给 Jev
```

**使用**：运行 `jev`，然后说：

```text
露娜 打开 Safari
露娜 去 youtube
露娜 搜索 youtube 上的 lofi 音乐
露娜 把音量调大
露娜 截个屏
露娜 打开备忘录输入买牛奶          # 复合：先打开备忘录，再输入
```

喊一次「露娜」后有 10 秒免唤醒窗口，可连续下指令；超时后再喊一次即可。

**要点**：

- 中文识别需 **多语言模型**（如 `models/ggml-small.bin`）；上面配置已指向它。
- 运行依赖仅 `pyobjc-framework-cocoa`、`pyobjc-framework-quartz`、`sounddevice`；HTTP、音频缓冲、Whisper 客户端均用标准库，系统工具用 `open` / `osascript` / `screencapture` / `pmset`。
- 唤醒词、语言、VAD、连续对话窗口等都在 `.env` 中配置，**无需改代码**。
- 英文逻辑保持兼容：英文唤醒词与英文指令照常可用。

## Setup (macOS, Apple Silicon)

```sh
cp .env.example .env                       # add your TYPESAFE_API_KEY from console.typesafe.ai
./scripts/setup.sh
```

The script installs whisper-cpp, downloads the model, creates the Python venv,
remaps **Caps Lock → F18** with `hidutil` (persisted by a LaunchAgent so it
survives reboots), installs a `jev` launcher in `~/.local/bin`, and opens the
three permission panes. Grant the terminal app you launch from (Cursor / Terminal /
iTerm) **Microphone**, **Accessibility** and **Input Monitoring**. If a permission
is missing at launch, Jev Voice prompts for it and waits.

Runtime dependencies are only `pyobjc-framework-cocoa`, `pyobjc-framework-quartz`
and `sounddevice`; HTTP, audio buffers and the Whisper client use the standard
library, and system tools (`open`, `osascript`, `screencapture`, `pmset`) do the
rest.

Undo the Caps Lock remap any time: `./scripts/uninstall-capslock.sh`.

## Run

```sh
jev                                 # hands-free: "Alfred, open chrome" (or tap CAPS LOCK, then speak)
jev --hold                          # hold CAPS LOCK to talk, release to run; no wake word
jev --always-on                     # open mic, EVERY utterance is a command (no wake word)
jev --ptt                           # push-to-talk in the terminal: Enter start / Enter stop
jev --device "RØDE"                 # pick a mic (.venv/bin/python -m sounddevice)
jev --text "open chrome and go to youtube" --dry-run   # test routing, no mic
```

**Hands-free mode (default):** the mic stays open and whisper transcribes every
utterance locally (~100 ms, nothing leaves the machine). Only utterances that name
the assistant (`WAKE_WORDS` in `.env`, default Alfred / Jarvis) go to Jev. After a
command you have `FOLLOWUP_SECONDS` (8) to chain more without the name: "Alfred,
open chrome" … "go to youtube" … "scroll down". Saying just "Alfred" chimes and
arms the next utterance. A Caps Lock tap does the same.

**Caps Lock modes (`--hold`):** hold it while speaking (Tink = recording, Pop = sent). A
short tap (<250 ms) latches hands-free recording; tap again to send. Caps Lock no
longer toggles capitals while the remap is installed.

## What you can say

| Say | Does |
| --- | --- |
| "open cursor", "switch to chrome" | `open -a` the matching installed app (Jev picks from the real app list) |
| "go to youtube", "go to stripe dot com" | opens the site |
| "search youtube for lofi hip hop", "google best ramen near me" | site-specific search |
| "type hello world and hit enter" | types into the focused field, optional submit |
| "close this tab", "select all and copy", "undo", "go back", "reload" | ~45 keyboard shortcuts |
| "scroll down a lot", "go to the top" | real scroll-wheel events |
| "volume up", "mute", "pause the music", "next song" | system volume / media keys |
| "take a screenshot", "open my downloads", "lock the screen", "toggle dark mode" | misc |
| "open notes and type buy milk and press enter" | compound: Jev flags it, code splits it, each step runs in order |

## How the Jev layer works (`jev_voice/brain.py`)

One request per utterance with ~15 speculative questions evaluated in parallel:

- `action` — Choice over 13 action kinds.
- `app` — Choice over your installed apps (+ `none`); `site`, `engine`, `folder`,
  `shortcut`, `scroll_dir`, `volume_op`, `media_op`, `system_op` — Choices over
  closed sets whose keys are exactly what the executor accepts.
- `text` — Choice over **candidate spans** cut from the transcript by regex
  ("type X", "search for X", quoted text, whole utterance). Jev picks the one that
  is exactly the payload. This is the "select instead of generate" pattern.
- `submit`, `compound` — Nouls.

Code reads only the answers the chosen action needs. Plan confidence is the
minimum over the judgements used. Below `ACTION_MIN_CONFIDENCE` (0.35) it says
"not sure" instead of acting. Thresholds live in `jev_voice/config.py`.

## Latency (Mac mini M4, measured)

| Stage | Time |
| --- | --- |
| End-of-speech detection | 550 ms of silence (tune `VADConfig.end_silence_ms`) |
| whisper.cpp base.en | 80–130 ms |
| Jev fan-out | 170–420 ms |
| Execute + `say` | ~50–100 ms |

## Floating transcription pill

A small always-on-top bar at the top-center of the screen shows what whisper
heard, what Jev decided, and the result (gray idle · red listening · yellow
heard · blue thinking · green done · orange error). It never takes keyboard
focus. `OVERLAY=0` or `--no-overlay` hides it.

## Feedback

`FEEDBACK=ding` (default) plays a chime when an action completes and a low buzz
on failure. `FEEDBACK=voice` gives spoken replies from a posh butler persona
(`PERSONA=alfred`, or `cowboy`) using the best British voice installed, or
ElevenLabs if `ELEVENLABS_API_KEY` is set (phrases cached to disk, so repeats are
instant).

## Layout

```
jev_voice/
  main.py     loop, CLI, compound handling
  brain.py    Jev questions, candidate extraction, Plan
  actions.py  macOS execution (open, keystrokes, scroll, volume, media keys…)
  audio.py    mic + VAD endpointing
  stt.py      whisper-server client
  net.py      stdlib HTTP client with connection reuse (replaces httpx)
  pcm.py      stdlib audio buffers (replaces numpy)
  tts.py      macOS `say`
  config.py   env / thresholds
  hotkey.py   Caps Lock (remapped to F18) global key tap
  overlay.py  floating transcription pill (AppKit)
  persona.py  butler / cowboy phrasing
scripts/
  setup.sh    one-shot install: deps, model, Caps Lock remap, launcher, permissions
```

## License

MIT
