# 打包部署指南

**最後更新**：2026-04-13

本文檔說明如何將 AI STT GUI 應用程式打包為 Windows 可執行檔 (.exe)。

## 快速開始

```powershell
cd D:\Python\meeting_stt_transcription
D:\conda_envs\lang_learn\python.exe build_exe.py
```

## 打包前準備

### 1. 環境檢查

```powershell
# 啟動 Conda 環境
conda activate lang_learn

# 檢查必要套件
python -c "import soundcard, soundfile, whisper, faster_whisper, torch; print('✓ 所有依賴已安裝')"

# 安裝 PyInstaller
pip install pyinstaller
```

### 2. 資源檢查

**必要資源**：
- [ ] `ai_transcriber_gui/ffmpeg/bin/ffmpeg.exe` 存在
- [ ] `ai_transcriber_gui/model/faster-whisper/faster-whisper-base/` 包含模型檔案
- [ ] `ai_transcriber_gui/STT(語音轉文字)程式使用說明.txt` 存在

**檢查指令**：
```powershell
# 檢查 ffmpeg
Test-Path "ai_transcriber_gui\ffmpeg\bin\ffmpeg.exe"

# 檢查模型
Test-Path "ai_transcriber_gui\model\faster-whisper\faster-whisper-base\config.json"
```

## 打包流程

### 執行打包腳本

```powershell
D:\conda_envs\lang_learn\python.exe build_exe.py 2>&1 | Tee-Object -FilePath build.log
```

**預期輸出**：
```
============================================================
AI STT GUI 打包工具
============================================================

步驟 1/5: 準備建置目錄...
Copied source to D:\Python\meeting_stt_transcription\build_pack

步驟 2/5: 修補 main.py（exe-relative paths）...
Patched main.py in build copy to use exe-relative RECORDINGS_DIR/EXPORTS_DIR/MODEL_DIR

步驟 3/5: 執行 PyInstaller（可能需要數分鐘）...
Running PyInstaller:
...

步驟 4/5: 複製模型檔案到 dist/...
Copied model/ to D:\Python\meeting_stt_transcription\dist\model

步驟 5/5: 清理暫存檔案...

============================================================
✓ 打包完成！
============================================================

輸出位置: D:\Python\meeting_stt_transcription\dist

使用說明：
  1. 將 model/ 資料夾放置於 .exe 同層目錄
  2. 首次執行會自動建立 recordings/ 和 exports/
  3. 確保 ffmpeg 已打包進 exe（whisper assets 同理）

============================================================
```

### 打包後檢查

```powershell
# 檢查 exe 是否存在
Test-Path "dist\AI_STT_Transcriber.exe"

# 檢查模型是否複製
Test-Path "dist\model\faster-whisper\faster-whisper-base\config.json"

# 檢查 exe 大小（應該 100-500 MB 之間）
(Get-Item "dist\AI_STT_Transcriber.exe").Length / 1MB
```

## 功能測試

### 基本測試清單

**在 dist/ 目錄執行**：
```powershell
cd dist
.\AI_STT_Transcriber.exe
```

**測試項目**：
- [ ] 程式正常啟動，顯示 GUI 視窗
- [ ] 狀態顯示「硬體加速: CUDA」或「硬體加速: CPU」
- [ ] 模型選單可正常切換
- [ ] 語言模式選單可正常切換
- [ ] 錄音來源選單可正常切換

**錄音測試**：
- [ ] 點選「開始錄音」(麥克風)，音量條有反應
- [ ] 勾選「即時轉錄」，轉錄結果即時顯示
- [ ] 點選「停止錄音」，產生 recordings/*.wav
- [ ] 轉錄完成後產生 exports/*.txt

**選檔測試**：
- [ ] 點選「選取檔案」，可選擇音訊/影片檔
- [ ] 分段轉錄（勾選即時）進度條正常更新
- [ ] 批次轉錄（不勾選即時）一次顯示完整結果
- [ ] 轉錄完成後產生 exports/*.txt

**UI 功能測試**：
- [ ] 「清除」按鈕可清空轉錄結果視窗
- [ ] 「停止轉錄」按鈕可中斷進行中的轉錄
- [ ] 系統訊息區正常顯示狀態訊息

## 分發打包

### 最小分發包

```
AI_STT_Transcriber/
├── AI_STT_Transcriber.exe          # 主程式 (~300 MB)
└── model/                           # 模型資料夾
    └── faster-whisper/
        └── faster-whisper-base/     # 基礎模型 (~150 MB)
            ├── config.json
            ├── model.bin
            ├── tokenizer.json
            └── vocabulary.txt
```

**總大小**：約 450 MB

### 完整分發包

```
AI_STT_Transcriber/
├── AI_STT_Transcriber.exe
├── model/
│   └── faster-whisper/
│       ├── faster-whisper-base/     # 基礎模型
│       ├── faster-whisper-small/    # 小型模型 (~500 MB)
│       └── faster-whisper-medium/   # 中型模型 (~1.5 GB)
├── recordings/                      # (選用) 範例錄音
├── exports/                         # (選用) 範例轉錄
└── README.txt                       # 使用說明
```

### 彈性打包策略 (動態模型載入)

**程式會自動掃描 `model/` 資料夾**，根據實際存在的模型建立選單。這使得你可以打包不同版本：

**策略 1：最小包 (base-only)**
```
model/
└── faster-whisper/
    └── faster-whisper-base/         # 僅包含 base 模型
```
→ UI 選單只顯示 `faster-whisper-base`

**策略 2：雙模型包 (base + small)**
```
model/
└── faster-whisper/
    ├── faster-whisper-base/
    └── faster-whisper-small/
```
→ UI 選單顯示兩個選項

**策略 3：完整包 (所有模型)**
```
model/
└── faster-whisper/
    ├── faster-whisper-base/
    ├── faster-whisper-small/
    └── faster-whisper-medium/
```
→ UI 選單顯示所有三個選項

**優點**：
- 無需修改程式碼即可調整模型組合
- 簡化打包流程（只需複製/刪除模型資料夾）
- 測試版可使用最小包快速分發
- 正式版可提供完整包滿足進階需求

## 疑難排解

### 打包失敗

**錯誤**：`ModuleNotFoundError: No module named 'PyInstaller'`  
**解決**：
```powershell
conda activate lang_learn
pip install pyinstaller
```

**錯誤**：`FileNotFoundError: whisper/assets not found`  
**解決**：build_exe.py 會自動處理，確認 whisper 已正確安裝：
```powershell
python -c "import whisper; print(whisper.__file__)"
```

### 執行時錯誤

**錯誤**：「找不到模型」  
**原因**：model/ 資料夾未放置於 exe 同層目錄  
**解決**：
```powershell
# 從原始碼目錄複製
Copy-Item -Recurse ai_transcriber_gui\model\ dist\model\
```

**錯誤**：「無法轉換音訊」  
**原因**：ffmpeg 未正確打包  
**檢查**：
```powershell
# 執行打包時應該看到：
# --add-data "ai_transcriber_gui\ffmpeg;ffmpeg"
```

**錯誤**：轉錄結果亂碼  
**原因**：whisper assets 未正確打包  
**檢查**：build.log 中應該出現：
```
Bundling whisper assets from: C:\...\whisper\assets
```

### 效能問題

**問題**：exe 啟動很慢 (>10 秒)  
**原因**：onefile 模式需要解壓縮到暫存目錄  
**解決**：正常現象，首次啟動較慢

**問題**：exe 檔案太大 (>1 GB)  
**檢查**：是否正確排除不需要的模組  
**解決**：檢查 build_exe.py 的 EXCLUDE_MODULES 設定

## 進階配置

### 修改 exe 名稱

編輯 `build_exe.py`:
```python
spec_args = [
    ...
    '--name=My_Custom_Name',  # 修改這裡
]
```

### 新增 exe 圖示

1. 準備 `.ico` 圖示檔
2. 編輯 `build_exe.py`:
```python
spec_args = [
    ...
    '--icon=path/to/icon.ico',
]
```

### 切換為資料夾模式（更快啟動）

編輯 `build_exe.py`:
```python
spec_args = [
    '--noconfirm',
    # '--onefile',  # 註解掉這行
    '--windowed',
    '--clean',
]
```

輸出會變成 `dist/AI_STT_Transcriber/` 資料夾，內含多個 DLL 和 exe。

## 更新流程

### 更新程式碼

1. 修改原始碼 (`ai_transcriber_gui/`)
2. 重新執行打包：
   ```powershell
   python build_exe.py
   ```
3. 保留 `dist/model/` 資料夾不變
4. 替換 `dist/AI_STT_Transcriber.exe`

### 更新模型

直接替換 `dist/model/faster-whisper/` 內的模型資料夾，不需要重新打包。

## 參考資訊

- **PyInstaller 官方文檔**：https://pyinstaller.org/en/stable/
- **Faster-Whisper 模型**：https://huggingface.co/Systran/faster-whisper-base
- **FFmpeg 官網**：https://ffmpeg.org/

---

**維護者**：AI STT GUI Development Team  
**最後測試**：2026-04-13  
**測試環境**：Windows 11, Python 3.12, CUDA 12.1
