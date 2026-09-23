# Jev Voice 使用指南

用语音控制 Mac：说话即可打开 App、输入文字、搜索、滚动、按快捷键。除一次约 250ms 的 **Jev**（TypeSafe System One 模型）调用外，所有处理都在本机完成。

```
麦克风 ─► 能量 VAD ─► whisper.cpp（Metal，本地，约 100ms） ─► Jev（1 次请求，约 250ms） ─► macOS 动作 ─► `say`/音效
```

Jev 不生成文本：代码从你的话里切出候选值，Jev 只负责**从闭集里选择**；执行由普通 Python 代码完成。

> 本指南对应「瘦身依赖」版本：运行时 pip 依赖仅 `pyobjc-framework-cocoa`、`pyobjc-framework-quartz`、`sounddevice`，HTTP/音频缓冲/Whisper 客户端均用标准库。

---

## 1. 环境要求

- macOS（面向 Apple Silicon；whisper.cpp 使用 Metal 加速）
- Python ≥ 3.12
- Homebrew
- 一个 **TypeSafe API key**（在 <https://console.typesafe.ai> 获取）
- 磁盘：whisper 模型约 142MB（`models/ggml-base.en.bin`）

> 识别语言为**英文**（whisper `-l en`，`ggml-base.en`）。请用**英文**说指令；中文解说仅供参考。

---

## 2. 安装

```sh
cp .env.example .env          # 填入 TYPESAFE_API_KEY
./scripts/setup.sh
```

`setup.sh` 会：

1. 安装 Homebrew 包 **whisper-cpp**（提供 `whisper-server`）
2. 下载模型到 `models/ggml-base.en.bin`
3. 创建 `.venv` 并 `pip install -e .`
4. 用 `hidutil` 把 **Caps Lock → F18**，并写入 `~/Library/LaunchAgents/ai.jev.capslock.plist`（重启后仍生效）
5. 在 `~/.local/bin/jev` 安装启动器，并打开三个权限设置面板

安装后**重启终端**，然后运行 `jev`。

### 2.1 系统权限

给**运行它的终端 App**（Cursor / Terminal / iTerm）授予：

| 权限 | 用途 |
|---|---|
| **Microphone** | 采集语音 |
| **Accessibility** | 全局按键监听、`keystroke` 输入、部分快捷键 |
| **Input Monitoring** | Caps Lock（F18）全局按键监听 |
| **Automation** | `osascript` 控制 `System Events`（首次会弹窗询问） |

截图指令通常还需要 **Screen Recording** 权限。缺少权限时程序会提示并等待。

---

## 3. 运行模式

| 命令 | 说明 |
|---|---|
| `jev` | **免手持（默认）**：麦克风常开，只有提到唤醒词的语句才发给 Jev |
| `jev --hold` | 按住 **CAPS LOCK** 说话，松开执行；短按（<250ms）切换免手持录制 |
| `jev --always-on` | 麦克风常开，**每句话**都当作指令（无需唤醒词） |
| `jev --ptt` | 终端里按 **Enter** 开始/停止录音 |
| `jev --text "..."` | 用文本代替麦克风跑一条指令 |
| `jev --text "..." --dry-run` | 只用 Jev 规划，**不触碰电脑** |
| `jev --device "RØDE"` | 指定麦克风（列出设备：`.venv/bin/python -m sounddevice`） |
| `jev --quiet` | 不朗读回复 |
| `jev --no-overlay` | 不显示悬浮字幕条（也可设 `OVERLAY=0`） |

### 3.1 唤醒词与连续对话

- 默认唤醒词：`WAKE_WORDS` = `alfred,jarvis,alfie,alford,elfred`
- 例：「**Alfred, open chrome**」；单独说「**Alfred**」会响一声并arm下一句
- 一条指令后 `FOLLOWUP_SECONDS`（默认 **8** 秒）内可**不喊名字**接着说：
  「Alfred, open chrome」→「go to youtube」→「scroll down」
- `--hold` 模式下 Caps Lock 不再切换大小写（已被重映射为 F18）

---

## 4. 支持的指令能力

Jev 每次会一次性问约 15 个并行问题（`action`、`app`、`site`、`engine`、`text`、`shortcut`、`scroll_dir`、`volume_op`、`media_op`、`system_op`、`folder`、`submit`、`compound`、`addressed`、`in_app`），代码只读取被选中动作所需的答案。

| 能力 | 触发方式（示例，英文） |
|---|---|
| 打开 / 切换 App | `open chrome`、`switch to cursor`、`open notes` |
| 打开网站 | `go to youtube`、`go to stripe dot com`、`open reddit` |
| 站内 / 网页搜索 | `search youtube for lofi beats`、`google best ramen near me`、`find github` |
| 输入文字 | `type hello world`、`write buy milk in the notes app` |
| 新建 | `new note`、`new tab`、`new document called groceries` |
| 快捷键（约 43 个） | `copy`、`paste`、`undo`、`save`、`switch app` 等 |
| 滚动 | `scroll down`、`scroll up a lot`、`go to the top`、`go to the bottom` |
| 音量 | `volume up`、`volume down`、`mute`、`unmute`、`max volume`、`half volume` |
| 媒体播放 | `pause the music`、`next song`、`previous track`、`play` |
| 截图 | `take a screenshot`（保存到桌面） |
| 打开文件夹 | `open my downloads`、`open documents`、`open the trash` |
| 系统 | `lock the screen`、`sleep the display`、`show the desktop`、`toggle dark mode`、`empty the trash` |
| 复合指令 | `open chrome and go to youtube`、`open notes and type buy milk and press enter` |

### 4.1 可用网站与搜索引擎（`site` / `engine`）

- **网站**：`youtube google gmail google_calendar google_drive google_docs google_maps github twitter_x reddit amazon netflix chatgpt claude notion spotify_web linkedin instagram facebook wikipedia hacker_news twitch figma typesafe_console`
- **搜索引擎**：`google youtube amazon wikipedia github google_maps twitter_x reddit spotify perplexity`

### 4.2 常用快捷键（`shortcut`）

`enter escape tab space backspace`、方向键、`copy paste cut`、`undo redo`、`select all`、`save`、`find`、`new`、`new tab`、`close tab`、`reopen closed tab`、`quit app`、`minimize window`、`hide app`、`fullscreen`、`next tab`、`previous tab`、`go back`、`go forward`、`reload`、`address bar`、`spotlight`、`switch app`、`next window`、`delete word`、`delete line`、`zoom in`、`zoom out`、`bold`、`italic`、`send message`、`emoji picker`

### 4.3 文件夹、音量、系统操作键值

- **文件夹 `folder`**：`home desktop downloads documents pictures movies applications trash`
- **音量 `volume_op`**：`up down mute unmute max half`
- **媒体 `media_op`**：`play_pause next previous`
- **滚动 `scroll_dir`**：`down up top bottom`；**`scroll_amount`**：`little page a_lot`
- **系统 `system_op`**：`lock sleep_display show_desktop toggle_dark_mode empty_trash`

---

## 5. 常用场景示例

> 下面是可直接照说的英文指令；`{}` 表示替换成你自己的内容。

### 5.1 应用与窗口

```text
open chrome
switch to cursor
open notes
quit spotify
minimize the window
hide the app
toggle fullscreen
new tab
close this tab
reopen the closed tab
```

### 5.2 网页与搜索

```text
go to youtube
open github
go to stripe dot com
search youtube for lofi beats
google best ramen near me
search github for swift concurrency
look up the weather in tokyo
```

### 5.3 输入与发送

```text
type hello world
type hello world and hit enter
write buy milk in the notes app
send the message
new note called groceries
new document titled weekly report
```

### 5.4 编辑与快捷键

```text
select all
copy
paste
undo
redo
save
find
zoom in
make the selection bold
open the emoji picker
open spotlight
```

### 5.5 阅读与滚动

```text
scroll down
scroll down a lot
scroll up a little
go to the top
go to the bottom
```

### 5.6 音量与媒体

```text
volume up
volume down
mute
unmute
max volume
half volume
pause the music
next song
previous track
```

### 5.7 系统与截屏

```text
take a screenshot
open my downloads
open documents
lock the screen
sleep the display
show the desktop
toggle dark mode
empty the trash
```

### 5.8 复合指令（一句多步）

```text
open chrome and go to youtube
open notes and type buy milk and press enter
new tab and go to github
```

### 5.9 连续对话（免手持）

```text
Alfred, open chrome
go to youtube
search for lofi hip hop
scroll down
Alfred, volume up
```

### 5.10 调试（不触碰电脑）

```sh
jev --text "open chrome and go to youtube" --dry-run   # 只看 Jev 的规划结果
jev --text "search youtube for lofi beats" --dry-run
jev --text "take a screenshot" --dry-run
```

输出形如：

```text
→ web_search(engine='youtube', query='lofi beats', compound=False, addressed=0.95)  conf=0.99  450ms
```

`conf` 低于 `ACTION_MIN_CONFIDENCE`（默认 **0.35**）时，程序会回一句「not sure」而不执行。

---

### 5.11 中文指令（需多语言模型）

`.env`：

```env
WHISPER_MODEL=/绝对路径/models/ggml-small.bin   # 多语言模型（不是 .en 版）
WHISPER_LANG=zh
WHISPER_TRANSLATE=0                             # 中文直接交给 Jev，无需翻译
WAKE_WORDS=露娜,路那,路纳,路納,入那,luna           # 唤醒词 + 同音变体
```

可直接说（Jev 天生懂中文，无需先翻成英文）：

```text
露娜 打开 Safari
露娜 去 youtube
露娜 搜索 youtube 上的 lofi 音乐
露娜 把音量调大
露娜 静音
露娜 往下滚动
露娜 截个屏
露娜 打开下载文件夹
露娜 锁屏
露娜 暂停音乐
露娜 复制
露娜 新建笔记叫购物清单
露娜 打开备忘录输入买牛奶          # 复合：先开备忘录，再输入
```

提示：

- 唤醒词建议列几个**同音变体**（识别可能写成 路那/路纳/入那/Runa 等）。
- 识别质量取决于模型：`ggml-small.bin` 够用；追求更稳可换 `ggml-medium.bin` / `ggml-large-v3.bin`（**不要**用 `large-v3-turbo`，它不支持翻译；若只想中文转写则可用）。
- `WHISPER_TRANSLATE=1` 可让“任意语言语音 → 英文”，但会**经常丢掉开头的唤醒词**、且短句翻译质量一般，不推荐与“必须唤醒词”搭配。

## 6. 配置项（`.env`）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `TYPESAFE_API_KEY` | — | **必填**，Jev API key |
| `TYPESAFE_URL` | `https://api.typesafe.ai/v1/systemone` | Jev 端点 |
| `JEV_MODEL` | `jev-latest` | 模型名 |
| `ACTION_MIN_CONFIDENCE` | `0.35` | 低于此值的规划不执行 |
| `WAKE_WORDS` | `alfred,jarvis,alfie,alford,elfred` | 唤醒词，逗号分隔；支持多词短语（如 `hey max`）、标点容错，以及**中文唤醒词与变体**（如 `露娜,路那,路纳,luna`） |
| `FOLLOWUP_SECONDS` | `8` | 指令后的免唤醒窗口（秒） |
| `UNNAMED_COMMANDS` | `1` | 未喊唤醒词时，是否让 Jev 判断是否是命令 |
| `UNNAMED_MIN_ADDRESSED` | `0.7` | 未命名语句的 `addressed` 阈值（`.env.example` 中为 `0`） |
| `UNNAMED_MIN_CONFIDENCE` | `0.7` | 未命名语句的置信度阈值（`.env.example` 中为 `0`） |
| `FEEDBACK` | `ding` | `ding` 音效 或 `voice` 语音回复 |
| `PERSONA` | `alfred` | `alfred` / `cowboy` / `plain` |
| `USER_NAME` | `Wayne` | 语音里称呼的名字 |
| `TTS_ENGINE` | 有 `ELEVENLABS_API_KEY` 则为 `elevenlabs`，否则 `say` | 语音合成引擎 |
| `TTS_VOICE` | 自动挑选 | `say` 的嗓音；不设则自动选 Premium/Enhanced |
| `TTS_RATE` | `210` | `say` 语速 |
| `ELEVENLABS_API_KEY` | — | 可选，启用 ElevenLabs |
| `ELEVENLABS_VOICE_ID` | 随 `PERSONA` | ElevenLabs 音色 |
| `WHISPER_MODEL` | `models/ggml-base.en.bin` | whisper 模型路径（中文需多语言模型，如 `models/ggml-small.bin`） |
| `WHISPER_LANG` | `en` | 识别语言：`zh` 中文、`en` 英文、`auto` 自动检测 |
| `WHISPER_TRANSLATE` | `0` | `1`=把识别结果翻成英文（需多语言模型；`large-v3-turbo` 不支持翻译） |
| `WHISPER_PORT` | `8178` | 本地 whisper-server 端口 |
| `WHISPER_THREADS` | `6` | whisper 线程数 |
| `VAD_PRE_ROLL_MS` | `240` | 语音开始前保留的音频（首字被吞就调大） |
| `VAD_END_SILENCE_MS` | `550` | 多少毫秒静音算说完（长句被截就调大） |
| `VAD_MIN_SPEECH_MS` | `250` | 短于此的片段丢弃 |
| `VAD_MAX_SPEECH_MS` | `12000` | 单句最长时长上限 |
| `VAD_START_FRAMES` | `3` | 连续多少帧够响才开始（调小更灵敏） |
| `VAD_THRESHOLD_MULT` | `3.5` | 触发阈值=底噪×该倍数（调小更灵敏） |
| `OVERLAY` | `1` | `0` 关闭悬浮字幕条 |
| `JEV_TTS_CACHE` | `~/.cache/jev-voice/tts` | 语音缓存目录 |

示例：

```env
TYPESAFE_API_KEY=apikey_xxx
FEEDBACK=voice
PERSONA=alfred
USER_NAME=Wayne
WAKE_WORDS=alfred,jarvis
FOLLOWUP_SECONDS=8
ACTION_MIN_CONFIDENCE=0.35
```

---

## 7. 故障排查

| 现象 | 处理 |
|---|---|
| 启动即报 `TYPESAFE_API_KEY is not set` | 确认 `.env` 存在且已填 key |
| `whisper-server not found` | `brew install whisper-cpp` |
| `Whisper model missing` | 重新运行 `./scripts/setup.sh`，或按提示 `curl -L -o models/ggml-base.en.bin ...` |
| 无法输入/按键无效 | 给终端授予 **Accessibility**；`osascript` 首次需 **Automation** 授权 |
| Caps Lock 无反应 | 需要 **Input Monitoring**；确认已运行 `setup.sh` 完成 `hidutil` 重映射 |
| 截图失败/空白 | 授予 **Screen Recording** |
| Jev 常回「not sure」 | 指令更明确，或调低 `ACTION_MIN_CONFIDENCE` |
| 环境里有旧 venv 出问题 | 删除 `.venv` 后重新 `python3 -m venv .venv && .venv/bin/pip install -e .` |
| 想先验证规划而不动手 | 加 `--dry-run` |

查看与重映射 Caps Lock：

```sh
hidutil property --get UserKeyMapping          # 查看当前映射
./scripts/uninstall-capslock.sh                # 撤销（或 hidutil property --set '{"UserKeyMapping":[]}'）
```

---

## 8. 卸载

```sh
./scripts/uninstall-capslock.sh     # 撤销 Caps Lock 重映射并删除 LaunchAgent
rm -rf .venv models                 # 删除本地环境与模型
rm -f ~/.local/bin/jev              # 删除启动器
```

---

## 9. 目录与外部依赖

```
jev_voice/
  main.py     主循环、CLI、复合指令处理
  brain.py    Jev 问题集、候选值切分、Plan
  actions.py  macOS 执行层（open、按键、滚动、音量、媒体键…）
  audio.py    麦克风采集 + VAD 端点检测
  stt.py      whisper-server 客户端
  net.py      标准库 HTTP 客户端（连接复用，替代 httpx）
  pcm.py      标准库音频缓冲（替代 numpy）
  tts.py      macOS `say` / ElevenLabs
  config.py   环境变量与阈值
  hotkey.py   Caps Lock（重映射为 F18）全局按键监听
  overlay.py  悬浮字幕条（AppKit）
  persona.py  语音人格措辞
scripts/
  setup.sh               一键安装
  uninstall-capslock.sh  撤销 Caps Lock 重映射
```

**外部资源**

- 运行时 pip 包：`pyobjc-framework-cocoa`、`pyobjc-framework-quartz`、`sounddevice`（含传递依赖 `pyobjc-core`、`cffi`、`pycparser`）
- Homebrew：`whisper-cpp`
- 系统命令：`open`、`osascript`、`say`、`afplay`、`screencapture`、`pmset`、`hidutil`
- 网络：**TypeSafe Jev**（必需）；**ElevenLabs**（可选）；Hugging Face（仅安装时下载模型）
- 本地文件：`~/Library/LaunchAgents/ai.jev.capslock.plist`、`~/.cache/jev-voice/tts/`、桌面截图
