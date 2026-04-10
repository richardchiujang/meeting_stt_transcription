---
name: workspace-instructions
description: "Use when: running or packaging the AI STT GUI app; quick run/build commands and where models/ffmpeg live. Applies to ai_transcriber_gui/*."
applyTo:
  "ai_transcriber_gui/**"
---

# Workspace instructions — AI 會話助手使用指南

目的：提供簡潔、可被 agent 自動載入的專案啟動、執行與打包指令，並指向更豐富的文件（README.md、project.md）。

主要內容（簡短清單）：

- **執行應用程式**
  - 安裝依賴： `pip install -r ai_transcriber_gui/requirements.txt`
  - 路徑 : `cd ai_transcriber_gui`  
  - 執行： `D:\conda_envs\lang_learn\python main.py`
  - python 使用 conda 環境： `D:\conda_envs\lang_learn\python`（請根據實際環境調整）

- **FFmpeg**
  - 請將 `ffmpeg/bin/ffmpeg.exe` 放置於 `ai_transcriber_gui/ffmpeg/bin`，或將系統 PATH 指向已安裝的 ffmpeg

- **模型檔案**
  - 模型重量檔（whisper / faster-whisper）請放在 `ai_transcriber_gui/model/`。這些大檔通常不會被版本控制。

- **打包為 .exe（簡要）**
  - 使用專案根目錄的 `build_exe.py`（本機需有 PyInstaller 與相容的 Python 環境）
  - 建議在專用的 Conda 環境中執行，或依 `project.md` 的說明操作

- **常用檔案（參考）**
  - 詳細說明： [project.md](project.md)
  - 專案總覽： [README.md](README.md)
  - 主程式： [ai_transcriber_gui/main.py](ai_transcriber_gui/main.py)
  - 依賴檔： [ai_transcriber_gui/requirements.txt](ai_transcriber_gui/requirements.txt)

Guidelines for agents and contributors:

- Prefer linking to the long-form docs (`project.md`, `README.md`) instead of duplicating them.
- Do not attempt to download or modify model weights automatically. If a task requires models, ask the user for approval.
- Use the `applyTo` glob to restrict instructions to files under `ai_transcriber_gui/` so agents only load this guidance for relevant requests.
- 用中文說明，因為專案主要是中文使用者和開發者。

If you want, I can also add example prompts (developer and user-facing) and a small troubleshooting checklist for common packaging errors.


