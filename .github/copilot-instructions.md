---
name: workspace-instructions
description: "AI STT GUI 應用程式開發指引"
applyTo:
  "ai_transcriber_gui/**"
---

# AI 會話助手 — 開發指引

## 執行環境

```powershell
# 執行
cd D:\Python\meeting_stt_transcription
D:\conda_envs\lang_learn\python.exe -m ai_transcriber_gui.main

# 測試
D:\conda_envs\lang_learn\python.exe -m ai_transcriber_gui.tests.test_mp3
```

- Python: `D:\conda_envs\lang_learn\python.exe` (Conda env: lang_learn)
- FFmpeg: `ai_transcriber_gui/ffmpeg/bin/ffmpeg.exe`
- 模型: `ai_transcriber_gui/model/` (不納入版控)
- 錄音/輸出: `recordings/`, `exports/` (專案根目錄)

## 核心架構

### 模組狀態

| 模組 | 功能 | 狀態 |
|------|------|------|
| `src/stt.py` | STT 引擎、模型載入 | ✅ |
| `src/utils.py` | 音檔轉換、重採樣 | ✅ |
| `src/recorder.py` | 單軌錄音 (麥克風/系統音) | ✅ |
| `src/devices.py` | 裝置列舉 | ✅ |
| `src/ui.py` | GUI 元件 | ✅ |
| `src/transcript.py` | 逐字稿處理 | ✅ |

### 設計原則

- **單一錄音來源**：一次只錄麥克風或系統音，不混音
- **UI 分區**：轉錄結果 / 系統訊息分開顯示
- **模組化**：業務邏輯在 `src/`，`main.py` 只做流程編排
- **語言設定**：所有 STT 方法統一傳遞 `language` + `initial_prompt`

## 技術要點

### 系統音錄音 (Loopback)
- 使用 `sc.all_microphones(include_loopback=True)` 列舉裝置
- 以 `dev.isloopback` 屬性篩選 loopback 裝置
- 採用裝置原生 samplerate (通常 48kHz)

### Whisper 語言設定

**語言映射**：
- 主要中文 → `language='zh'`, prompt="以繁體中文為主，夾雜英文術語。"
- 主要英文 → `language='en'`, prompt="This is a technical meeting in English."
- 系統自動判斷 → `language=None`, prompt="繁體中文與英文混合討論。"

**統一傳遞**：所有轉錄方法 (`transcribe_chunk`, `transcribe_file_stream`, `transcribe_file_to_text`) 都接收 `language` 和 `initial_prompt` 參數。

**Prompt 過濾**：`transcribe_chunk` 會自動過濾與 prompt 相同的結果，使用多重策略：
1. 完全相同比對
2. Prompt 佔比檢查（>80%）
3. 反向子字串檢查（處理 prompt 變體）
4. 特徵詞過濾（「混合討論」等標誌詞）

避免 Whisper 在無語音/低質量音訊時輸出 prompt 內容。注意「系統自動判斷」使用中文 prompt，避免引導 Whisper 誤判為英文。

### 按鈕狀態邏輯
- 即時轉錄模式：「停止錄音並轉錄」按鈕 DISABLED
- 非即時模式：「停止錄音並轉錄」按鈕 ENABLED
- 勾選即時轉錄時自動調整按鈕狀態

### 模型掃描機制
- **啟動時掃描**：程式啟動時自動掃描 `model/` 資料夾
- **Faster-Whisper 偵測**：檢查 `model/faster-whisper/*/config.json` 存在性
- **OpenAI Whisper 偵測**：檢查 `model/whisper/*.pt` 檔案
- **容錯機制**：未找到任何模型時使用預設清單，避免程式無法啟動
- **彈性部署**：不同打包可提供不同模型組合（base-only / full）

## 修改規則

- ⛔ 不自動下載或修改模型檔案
- ⛔ 不新增混音、雙軌合成功能
- ⛔ 不把系統訊息寫入轉錄結果區
- ✅ 說明與註解請用中文
- ✅ 新功能優先放入 `src/` 模組
- ✅ 所有流程結束顯示「✓ 已完成」

## 打包注意事項

- 使用 `build_exe.py` 打包，會自動修補路徑
- 打包後 exe 使用 `sys._MEIPASS` 存取 bundled assets (ffmpeg, whisper assets)
- 使用者資料 (recordings, exports, model) 放置於 exe 同層目錄
- 新增功能時確認不引入需要額外打包的大型依賴
- UI 變更不影響打包配置

