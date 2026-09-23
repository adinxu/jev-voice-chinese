#!/bin/zsh
# One-shot setup for Jev Voice on macOS.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "▸ Homebrew deps"
command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
brew list --formula whisper-cpp >/dev/null 2>&1 || brew install whisper-cpp

echo "▸ Whisper model"
mkdir -p models
[ -f models/ggml-base.en.bin ] || curl -L -o models/ggml-base.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin

echo "▸ Python env"
[ -f .env ] || { echo "Missing .env with TYPESAFE_API_KEY=..."; exit 1; }
python3 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -e .

echo "▸ Caps Lock → F18 (hidutil), persisted with a LaunchAgent"
MAPPING='{"UserKeyMapping":[{"HIDKeyboardModifierMappingSrc":0x700000039,"HIDKeyboardModifierMappingDst":0x70000006D}]}'
hidutil property --set "$MAPPING" >/dev/null
AGENTS="$HOME/Library/LaunchAgents"; mkdir -p "$AGENTS"
cat > "$AGENTS/ai.jev.capslock.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>ai.jev.capslock</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/hidutil</string><string>property</string><string>--set</string>
    <string>$MAPPING</string>
  </array>
  <key>RunAtLoad</key><true/>
</dict></plist>
PLIST
launchctl bootout "gui/$(id -u)/ai.jev.capslock" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$AGENTS/ai.jev.capslock.plist"

echo "▸ 'jev' launcher in ~/.local/bin"
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/jev" <<LAUNCH
#!/bin/zsh
cd "$ROOT" && exec .venv/bin/python -m jev_voice.main "\$@"
LAUNCH
chmod +x "$HOME/.local/bin/jev"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc";; esac

echo "▸ Permissions (grant your terminal app: Cursor / Terminal / iTerm)"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
sleep 1
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
sleep 1
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"

echo
echo "✔ Done. Restart your terminal, then run:  jev"
echo "  Hold CAPS LOCK and speak. Tap CAPS LOCK to toggle hands-free."
echo "  Undo the remap any time:  hidutil property --set '{\"UserKeyMapping\":[]}'  and remove ~/Library/LaunchAgents/ai.jev.capslock.plist"
