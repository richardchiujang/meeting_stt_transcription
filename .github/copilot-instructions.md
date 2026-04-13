---
name: workspace-instructions
description: "Use when: running or packaging the AI STT GUI app; quick run/build commands and where models/ffmpeg live. Applies to ai_transcriber_gui/*."
applyTo:
  "ai_transcriber_gui/**"
---

# Workspace instructions — AI 會話助手使用指南

- **執行**（從專案根目錄）：
  ```powershell
  cd D:\Python\meeting_stt_transcription
  D:\conda_envs\lang_learn\python.exe -m ai_transcriber_gui.main
  ```
  - Python：`D:\conda_envs\lang_learn\python.exe`（Conda env `lang_learn`）
  - `recordings/` 與 `exports/` 位於**專案根目錄**，不在 `ai_transcriber_gui/`

- **FFmpeg**：`ai_transcriber_gui/ffmpeg/bin/ffmpeg.exe`
- **模型**：`ai_transcriber_gui/model/`（不納入版本控制）
- **打包**：`D:\conda_envs\lang_learn\python.exe build_exe.py`（見 [project.md](project.md)）

- **測試**：
  ```powershell
  D:\conda_envs\lang_learn\python.exe -m ai_transcriber_gui.tests.smoke_test
  D:\conda_envs\lang_learn\python.exe -m ai_transcriber_gui.tests.test_mp3
  ```
  快速音檔：`recordings/bq96s64K2YM_30s.mp3`（30 秒）；完整：`recordings/bq96s64K2YM.mp3`（20 分鐘，216 segments）

- **參考文件**：[project.md](project.md)、[README.md](README.md)、[main.py](ai_transcriber_gui/main.py)

> 規則：勿自動下載或修改模型；說明請用中文。

## src/ 模組重構狀態

| 模組 | 路徑 | 狀態 |
|------|------|------|
| STT / Transcriber | `src/stt.py` | ✅ 完成 |
| Audio helpers | `src/utils.py` | ✅ 完成 |
| 錄音 / loopback | `src/recorder.py` | ⬜ 待完成 |
| 裝置列舉 | `src/devices.py` | ⬜ 待完成 |
| GUI / TranscriberApp | `src/ui.py` | ⬜ 待完成 |

**路徑重要異動**：`recordings/` 與 `exports/` 已移至專案根目錄；`main.py` 的 `PROJECT_ROOT`、`RECORDINGS_DIR`、`EXPORTS_DIR` 常數已更新。

**已驗證**：`faster-whisper-base` 在 20 分鐘英文音檔上產生 216 segments，language=English, prob=1.0 ✅

## Loopback 錄音架構（2026-04-12 修正完成）

- `scan_audio_devices`：用 `dev.isloopback` 分類 mic vs loopback；PyAudioWPatch 補充列舉
- `_device_map[name]` 存放 soundcard `Microphone` 物件（loopback）或 `('pyaudio', idx, info)` tuple
- 雙軌錄音用裝置原生 samplerate（`default_samplerate`，通常 48k）；`_mic_rec_fs` / `_loop_rec_fs` 記錄實際 fs
- PyAudio+soundcard 混合路徑：soundcard recorder 在 `while` 迴圈**外**以 `__enter__` 開啟，`finally` 中 `__exit__`
- `_save_recording_file`：即時模式停止時呼叫，讀 `_mic_rec_fs/_loop_rec_fs`，同 fs 時 mic+loopback 混音（×0.6 clip），輸出 mp3

