# AI 語音轉文字工具 (GUI 版)

最後更新：2026-04-13

本工具提供圖形介面，支援錄製麥克風或系統音、選取影音檔，使用地端 Whisper / faster-whisper 模型進行中英夾雜轉錄。

## 快速啟動

```powershell
cd D:\Python\meeting_stt_transcription
D:\conda_envs\lang_learn\python.exe -m ai_transcriber_gui.main
```

## 系統邏輯與架構

### 核心設計選擇

| 項目 | 方案 | 理由 |
|------|------|------|
| 錄音來源 | 單一來源（麥克風 OR 系統音） | 簡化流程，避免混音複雜度 |
| UI 分區 | 轉錄結果 + 系統訊息分離 | 避免污染逐字稿輸出 |
| 模型引擎 | faster-whisper 優先 | 同尺寸下速度 ≫ openai-whisper |
| 語言設定 | language + initial_prompt | 統一所有轉錄方法參數傳遞 |
| 檔案前處理 | 統一轉 16k mono WAV | 確保 STT 品質穩定 |
| 音檔存放 | 專案根目錄 recordings/ | 便於存取與管理 |

### 轉錄流程分類

| 模式 | 入口方法 | 特性 | 輸出文字檔 | 適用場景 |
|------|----------|------|-----------|----------|
| 錄音+即時 | `transcription_worker` | 累積 2.5 秒後轉錄，Queue 傳遞 chunk | ✅ 停止時輸出 | 會議即時記錄 |
| 錄音+非即時 | `transcribe_file_batch` | 錄完存檔後整檔轉錄 | ✅ 完成時輸出 | 後製處理 |
| 選檔+即時 | `transcribe_file_stream` | 分段讀取，進度回報 | ✅ 完成時輸出 | 大檔案預覽 |
| 選檔+非即時 | `transcribe_file_batch` | 整檔一次轉錄 | ✅ 完成時輸出 | 最終輸出 |

### 語言設定映射

```python
UI 選項          → Whisper 參數
─────────────────────────────────────────────────────
"主要中文"       → language='zh'
                  initial_prompt="以繁體中文為主，夾雜英文術語。"

"主要英文"       → language='en'
                  initial_prompt="This is a technical meeting in English. Use proper English spellings."

"系統自動判斷"   → language=None
                  initial_prompt="繁體中文與英文混合討論。"
```

**重要**：「系統自動判斷」使用中文 prompt，避免英文 prompt 引導 Whisper 將中文音訊誤判為英文。

### 按鈕狀態邏輯

```
狀態：即時轉錄已勾選
├─ 錄音中 → 「停止錄音並轉錄」DISABLED（不需要，按錄音鈕即停止）
└─ 未錄音 → 「停止錄音並轉錄」DISABLED

狀態：即時轉錄未勾選
├─ 錄音中 → 「停止錄音並轉錄」ENABLED（點擊後停止並開始轉錄）
└─ 未錄音 → 「停止錄音並轉錄」NORMAL
```

## 程式主流程圖

```
┌─────────────────────────────────────────────────────────────────┐
│                        啟動 GUI 應用程式                        │
│  - 初始化 Transcriber (STT engine)                              │
│  - 建立 UI 元件 (按鈕、下拉選單、結果區、系統訊息區)            │
│  - 設定音訊裝置來源 (麥克風/系統音)                             │
└─────────────────────┬───────────────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
      【錄音模式】            【選檔案模式】
          │                       │
    ┌─────┴─────┐          ┌──────┴──────┐
    │           │          │             │
 [即時]    [非即時]     [即時]      [非即時]
    │           │          │             │
    ↓           ↓          ↓             ↓
┌────────┐ ┌────────┐ ┌────────┐  ┌────────────┐
│邊錄邊轉│ │先錄後轉│ │分段轉錄│  │整檔一次轉錄│
│ (即時) │ │ (批次) │ │ (串流) │  │  (批次)    │
└────┬───┘ └───┬────┘ └───┬────┘  └──────┬─────┘
     │         │          │              │
     ↓         ↓          ↓              ↓
┌──────────────────────────────────────────────┐
│  transcription_worker / transcribe_file_stream│
│  - 使用選定的 Whisper 模型                    │
│  - 即時輸出到「轉錄結果」視窗                 │
│  - 批次模式完成後一次性顯示                   │
└────────────────┬─────────────────────────────┘
                 │
                 ↓
           ┌────────────┐
           │  STT 完成  │
           │ 儲存 txt   │
           │ 顯示「已完成」
           └────────────┘

【各模式說明】

1. 錄音 + 即時轉錄：
   - 按下「開始錄音」→ 勾選「即時轉錄」
   - 錄音的同時，音訊 chunk 放入 Queue
   - transcription_worker 背景執行緒持續從 Queue 取出並轉錄
   - 轉錄結果即時顯示在「轉錄結果」區
   - 按「開始錄音」（再次按）停止錄音，自動結束轉錄
   - 「停止錄音並轉錄」按鈕 DISABLED（因為即時模式不需要）

2. 錄音 + 非即時轉錄：
   - 按下「開始錄音」→ 不勾選「即時轉錄」
   - 單純錄音，音訊存入 buffer
   - 按「停止錄音並轉錄」→ 儲存 WAV → 呼叫 transcribe_selected_file
   - 整檔一次轉錄完成後顯示

3. 選檔案 + 即時轉錄：
   - 按「選取檔案」→ 勾選「即時轉錄」
   - 預處理音檔（轉成 16k mono WAV）
   - transcribe_file_stream 分段讀取並轉錄
   - 轉錄結果逐段顯示，進度條更新

4. 選檔案 + 非即時轉錄：
   - 按「選取檔案」→ 不勾選「即時轉錄」
   - 預處理音檔
   - 整檔一次轉錄
   - 完成後一次性顯示所有文字
```

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
├── recordings/              # 錄音檔 (專案根目錄)
├── exports/                 # 轉錄 txt 輸出
├── build_exe.py            # 打包腳本
└── ai_transcriber_gui/
    ├── main.py              # 入口與流程控制
    ├── ffmpeg/bin/          # ffmpeg.exe
    ├── model/               # Whisper 模型 (不納入版控)
    ├── src/
    │   ├── stt.py           # STT 引擎
    │   ├── utils.py         # 音訊處理
    │   ├── recorder.py      # 錄音功能
    │   ├── devices.py       # 裝置列舉
    │   ├── ui.py            # GUI 元件
    │   └── transcript.py    # 逐字稿處理
    └── tests/
        └── test_mp3.py      # 測試腳本
```

## 技術實作細節

### 系統音錄音 (Loopback)
- 使用 `soundcard.all_microphones(include_loopback=True)`
- 以 `device.isloopback` 屬性識別 loopback 裝置
- 採用裝置原生 samplerate (通常 48kHz)
- 錄音後轉存為 16k mono WAV 供 STT 使用

### 音訊處理流程
```
輸入檔案 (mp3/mp4/etc.)
  ↓
FFmpeg 轉換
  ↓
16kHz mono WAV
  ↓
Whisper 模型
  ↓
文字輸出
```

### Thread 安全設計
- 錄音在背景 thread 執行
- 使用 Queue 傳遞音訊 chunk 與 UI 更新
- 主執行緒用 `root.after()` 輪詢 Queue 更新 UI
- 避免跨 thread 直接操作 Tkinter 元件

## 安裝與環境

```bash
pip install -r ai_transcriber_gui/requirements.txt
```

- **Python**：`D:\conda_envs\lang_learn\python.exe`（Conda env: lang_learn）
- **FFmpeg**：`ai_transcriber_gui/ffmpeg/bin/ffmpeg.exe`
- **模型**：`ai_transcriber_gui/model/faster-whisper/` (不納入版控)

### 模型選擇

| UI 選項 | 路徑 | 特性 |
|---------|------|------|
| faster-whisper-base | model/faster-whisper/faster-whisper-base/ | 快速，測試用 |
| faster-whisper-small | model/faster-whisper/faster-whisper-small/ | 平衡速度與準確度 |
| faster-whisper-medium | model/faster-whisper/faster-whisper-medium/ | 最準確 |

Accuracy: base < small < medium  
Speed: faster-whisper ≫ openai-whisper (同尺寸)

## 打包部署

### 快速打包

```powershell
cd D:\Python\meeting_stt_transcription
D:\conda_envs\lang_learn\python.exe build_exe.py 2>&1 | Tee-Object -FilePath build.log
```

### 打包配置 (build_exe.py)

**核心設定**：
- **Conda 環境**：`D:\conda_envs\lang_learn`
- **輸出目錄**：`dist/`
- **Exe 名稱**：`AI_STT_Transcriber.exe`
- **模式**：`--onefile` (單一執行檔), `--windowed` (無 console 視窗)

**打包內容**：
| 項目 | 來源 | 目標位置 | 說明 |
|------|------|----------|------|
| ffmpeg | `ai_transcriber_gui/ffmpeg/` | exe 內部 (`sys._MEIPASS`) | 音訊轉換工具 |
| whisper assets | conda env site-packages | exe 內部 | mel_filters.npz 等 |
| 使用說明 | `STT(語音轉文字)程式使用說明.txt` | exe 內部 | 用戶指南 |
| **model/** | 手動複製 | exe 同層目錄 | Whisper 模型檔案 (不打包進 exe) |
| **recordings/** | 執行時自動建立 | exe 同層目錄 | 錄音輸出 |
| **exports/** | 執行時自動建立 | exe 同層目錄 | 轉錄文字輸出 |

**排除模組** (減少 exe 體積)：
```python
transformers.models.gemma*  # 不需要的 transformer 模型
matplotlib                  # 不使用繪圖功能
IPython, jupyter            # 不需要互動式環境
pytest                      # 不需要測試框架
```

### 打包流程

```
步驟 1/5: 準備建置目錄
  ├─ 複製 ai_transcriber_gui/ 到臨時資料夾 build_pack/
  
步驟 2/5: 修補 main.py
  ├─ 設定 exe-relative 路徑 (RECORDINGS_DIR, EXPORTS_DIR, MODEL_DIR)
  ├─ 確保打包後能正確存取資源
  
步驟 3/5: 執行 PyInstaller (可能需要數分鐘)
  ├─ 打包所有依賴模組
  ├─ 壓縮為單一 exe
  ├─ 產生 dist/AI_STT_Transcriber.exe
  
步驟 4/5: 複製模型檔案
  ├─ 將 ai_transcriber_gui/model/ 複製到 dist/model/
  
步驟 5/5: 清理暫存檔案
  └─ 刪除 build_pack/
```

### 部署檢查清單

**打包前**：
- [ ] 確認 Conda 環境已安裝所有依賴 (`pip install -r requirements.txt`)
- [ ] 確認 PyInstaller 已安裝 (`pip install pyinstaller`)
- [ ] 確認 ffmpeg 存在於 `ai_transcriber_gui/ffmpeg/bin/`
- [ ] 確認模型檔案存在於 `ai_transcriber_gui/model/faster-whisper/`

**打包後**：
- [ ] 檢查 `dist/AI_STT_Transcriber.exe` 是否存在
- [ ] 檢查 `dist/model/faster-whisper/` 是否包含模型
- [ ] 執行 exe 測試基本功能
- [ ] 確認錄音、轉錄、選檔功能正常

**分發時**：
```
AI_STT_Transcriber/
├── AI_STT_Transcriber.exe    # 主程式
├── model/                     # 模型資料夾 (手動複製)
│   ├── faster-whisper/
│   │   ├── faster-whisper-base/
│   │   ├── faster-whisper-small/
│   │   └── faster-whisper-medium/
│   └── whisper/               # (選用)
├── recordings/                # 自動建立
└── exports/                   # 自動建立
```

### 常見問題

**Q: 為什麼 model/ 不打包進 exe？**  
A: 模型檔案太大 (數百 MB ~ 數 GB)，打包進 exe 會導致：
   - exe 體積過大，難以分發
   - 啟動速度變慢
   - 更新模型需要重新打包
   
   解決方案：將 model/ 放置於 exe 同層目錄，程式會自動讀取。

**Q: 打包後執行顯示「找不到模型」？**  
A: 確認 `dist/model/faster-whisper/faster-whisper-base/` 路徑存在，且包含 `config.json` 等檔案。

**Q: 打包後轉錄顯示亂碼？**  
A: 檢查 whisper assets 是否正確打包 (build_exe.py 會自動處理)。

**Q: 如何更新程式？**  
A: 修改原始碼後重新執行 `build_exe.py`，保留 dist/model/ 資料夾即可。

## 測試

```powershell
# 快速測試 (30 秒音檔)
D:\conda_envs\lang_learn\python.exe -m ai_transcriber_gui.tests.test_mp3

# 測試檔案
recordings/bq96s64K2YM_30s.mp3  # 30 秒
recordings/bq96s64K2YM.mp3      # 20 分鐘 (216 segments)
```

## 已知注意事項

1. **系統音品質**：
   - 使用輸出裝置原生格式 (48kHz) 錄製
   - 避免強制 16kHz（Windows 重採樣會降低品質）

2. **麥克風音量**：
   - Intel Smart Sound / Realtek 陣列麥克風有 AEC/AGC/NS 處理
   - 音量忽大忽小屬正常現象

3. **即時轉錄延遲**：
   - chunk 大小影響延遲與準確度平衡
   - 預設 0.2 秒 chunk，可調整

4. **語言設定**：
   - **必須**選擇正確語言模式，否則辨識錯誤
   - 建議：純中文選「主要中文」，純英文選「主要英文」
