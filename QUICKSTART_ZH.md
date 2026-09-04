# MacBook 本地听写与会议纪要：解包运行说明

这个压缩包同时包含浏览器前端和 Python/MLX 后端。录音、听写和纪要均保存在
MacBook 本地。

## 系统要求

- Apple Silicon Mac（M1/M2/M3/M4 或更新）
- macOS 14 或更新版本
- 可用空间建议至少 8 GB
- 已安装 `uv`

如果尚未安装 `uv`，可以使用 Homebrew：

```bash
brew install uv
```

## 1. 解压

可以直接在 Finder 双击 ZIP，也可以在 Terminal 执行：

```bash
ditto -x -k macbook-live-meeting-notes-0.2.0-macos-arm64.zip .
cd macbook-live-meeting-notes-0.2.0-macos-arm64
```

## 2. 启动

```bash
chmod +x run.command
./run.command
```

首次启动会执行以下工作：

1. 使用锁定文件创建本地 Python 3.12 虚拟环境；
2. 下载并安装依赖；
3. 首次使用时下载 Nemotron ASR 和 Qwen3.5 4B 模型；
4. 打开 `http://127.0.0.1:8765`。

模型下载完成后会缓存在当前用户的 Hugging Face 缓存中，后续不必重复下载。
会议音频和文字不会上传到云端。

如果 macOS 阻止双击运行，请在 Terminal 中使用上面的 `./run.command` 命令，或在
Finder 中右键 `run.command`，选择 **Open**。

## 3. 实际使用

1. 在 **Microphone** 下拉框选择输入设备；保持 **Default microphone** 会使用
   macOS 当前系统默认麦克风。
2. 点击 **Start recording**。
3. 状态变为 **Listening on this Mac** 后开始讲话。
4. 点击 **Stop & save**，等待最终纪要完成。
5. 点击 **Open recordings folder** 在 Finder 查看结果。

每次录音会创建一个时间戳目录：

```text
sessions/2026-09-03_14-25-30/
  2026-09-03_14-25-30_audio.wav
  2026-09-03_14-25-30_transcript.txt
  2026-09-03_14-25-30_transcript.md
  2026-09-03_14-25-30_notes.md
  2026-09-03_14-25-30_events.jsonl
  2026-09-03_14-25-30_manifest.json
```

## 4. 停止程序

回到启动程序的 Terminal 窗口，按 `Control-C`。关闭浏览器标签页不会停止后台服务。

## 常见问题

### 页面按钮没有反应

先按 `Command-R` 刷新页面，再确认启动程序的 Terminal 窗口仍在运行。

### 没有麦克风声音

到 **System Settings → Privacy & Security → Microphone**，允许 Terminal 或启动该
程序的终端应用访问麦克风，然后重新启动程序。

### 更换端口或不自动打开浏览器

```bash
./run.command --port 8877
./run.command --no-open-browser --port 8877
```
