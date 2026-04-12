# AI 語音轉文字工具 (GUI 版)

最後更新：2026-04-13
本工具提供圖形介面，支援錄製麥克風或選取現有影音檔，使用地端 Whisper / faster-whisper 模型進行中英夾雜優化轉錄。

## 快速啟動

```powershell
cd D:\Python\meeting_stt_transcription
D:\conda_envs\lang_learn\python.exe -m ai_transcriber_gui.main
```

```powershell
# 測試
D:\conda_envs\lang_learn\python.exe -m ai_transcriber_gui.tests.smoke_test
D:\conda_envs\lang_learn\python.exe -m ai_transcriber_gui.tests.test_mp3
# 打包
D:\conda_envs\lang_learn\python.exe build_exe.py 2>&1 | Tee-Object -FilePath build.log
```

## 目錄結構

```text
meeting_stt_transcription/
├── recordings/              # mp3 錄音（含測試音檔）
│   ├── bq96s64K2YM_30s.mp3  # 快速測試（30 秒）
│   └── bq96s64K2YM.mp3      # 完整測試（20 分鐘，216 segments ✅）
├── exports/                 # 轉錄 txt
├── build_exe.py
├── project.md
└── ai_transcriber_gui/
    ├── main.py              # 入口（匯入 src.*）
    ├── requirements.txt
    ├── ffmpeg/bin/          # ffmpeg.exe
    ├── model/               # 模型（不納入版控）
    │   ├── faster-whisper/{faster-whisper-base,small,medium}/
    │   └── whisper/{base,small,medium}.pt
    ├── src/
    │   ├── stt.py           # Transcriber 類 ✅
    │   ├── utils.py         # audio helpers ✅
    │   ├── recorder.py      # 錄音/loopback ⬜
    │   ├── devices.py       # 裝置列舉 ⬜
    │   └── ui.py            # TranscriberApp ⬜
    └── tests/
        ├── smoke_test.py    ✅
        └── test_mp3.py      ✅
```

## 安裝

```bash
pip install -r ai_transcriber_gui/requirements.txt
```

FFmpeg 放在 `ai_transcriber_gui/ffmpeg/bin/ffmpeg.exe`（或加入系統 PATH）。

## 模型

| UI 選項 | 使用模型 | 說明 |
|---------|----------|------|
| base | faster-whisper-base | 快，適合測試 |
| small | faster-whisper-small | 平衡 |
| medium | faster-whisper-medium | 最準 |

Accuracy：base < small < medium；Speed（同尺寸）：faster-whisper ≫ openai-whisper

模型放在 `ai_transcriber_gui/model/faster-whisper/`，離線載入，不自動下載。

## 功能

- **麥克風錄音**：`soundcard` 錄製，存為 mp3（timestamp 命名）
- **影音檔轉錄**：支援 `.mp3 .wav .mp4 .mkv .m4a .mov .wmv`，FFmpeg 負責格式轉換
- **語言模式**：主要中文 / 主要英文 / 系統自動判斷（透過 `initial_prompt` 引導）
- **即時顯示**：切片 Queue 架構，邊錄邊轉，tkinter 不卡頓

## 打包 .exe

打包範圍：`main.py`、`src/`、`ffmpeg/`；**不打包** `model/`、`recordings/`、`exports/`（放在 .exe 同層目錄即可）。

```bash
pyinstaller --onefile --add-binary "ai_transcriber_gui/ffmpeg/bin/ffmpeg.exe;." --add-binary "path\to\portaudio.dll;." ai_transcriber_gui\main.py
```

## 音訊架構備忘（WASAPI Loopback）

> **目前實作**：純麥克風錄音（`soundcard.default_microphone()`），未啟用系統音捕捉。

若日後需要捕捉系統音（喇叭播放的聲音），正確做法：

- 使用 **PyAudioWPatch**（非標準 PyAudio），專為 Windows WASAPI loopback 打 patch 的 fork
- Loopback 裝置需以**輸出裝置 native format 錄製**（通常 48k/stereo），再離線 downsample 為 16k/mono 給 Whisper
- 避免直接用 16k 抓 loopback（Windows 即時 resample 會降低品質）
- 麥克風與系統音建議**分軌錄製再合併**（Whisper 對單一乾淨來源辨識率更高）

常見舊版 loopback 失敗原因：
1. 用 16k 直接抓（格式不符，Windows resample 糊化）
2. 走進 AEC/AGC/NS DSP 路徑（Intel Smart Sound / Realtek 麥克風陣列），聲音忽大忽小
3. sounddevice / soundcard 的 PortAudio build 不支援 loopback（誤以為在抓，實際上沒有）
