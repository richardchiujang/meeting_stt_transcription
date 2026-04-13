# AI 會議錄音轉文字（GUI 版）

**最後更新**：2026-04-13

本專案提供圖形介面的語音轉文字工具，支援錄製麥克風/系統音、選取影音檔案，使用地端 Whisper / faster-whisper 模型進行中英夾雜轉錄。

## 主要功能

- ✅ **雙音源錄音**：麥克風 / 系統音 (Loopback)
- ✅ **即時/批次轉錄**：邊錄邊轉或錄完再轉
- ✅ **多格式支援**：mp3, wav, mp4, mkv, m4a, mov, wmv
- ✅ **多模型選擇**：faster-whisper (base/small/medium), openai-whisper
- ✅ **語言優化**：主要中文、主要英文、系統自動判斷
- ✅ **進度顯示**：音量顯示、轉錄進度條
- ✅ **一鍵打包**：支援打包為 Windows .exe 單一執行檔

## 快速開始

### 開發環境執行

```powershell
cd D:\Python\meeting_stt_transcription
D:\conda_envs\lang_learn\python.exe -m ai_transcriber_gui.main
```

### 打包為 exe

```powershell
# 打包前檢查
python verify_package.py --pre

# 執行打包
python build_exe.py

# 打包後驗證
python verify_package.py --post
```

詳細說明請參閱 **[打包部署指南 (PACKAGING.md)](PACKAGING.md)**。

## 目錄結構

```text
meeting_stt_transcription/
├── ai_transcriber_gui/          # 主程式
│   ├── main.py                  # 入口
│   ├── src/                     # 核心模組
│   │   ├── stt.py              # STT 引擎
│   │   ├── ui.py               # GUI 介面
│   │   ├── recorder.py         # 錄音功能
│   │   ├── utils.py            # 音訊處理
│   │   ├── devices.py          # 裝置列舉
│   │   └── transcript.py       # 逐字稿處理
│   ├── ffmpeg/                  # FFmpeg 工具
│   └── model/                   # Whisper 模型 (不納入版控)
├── recordings/                  # 錄音輸出
├── exports/                     # 轉錄文字輸出
├── build_exe.py                # 打包腳本
├── verify_package.py           # 打包驗證腳本
├── PACKAGING.md                # 打包部署指南
└── project.md                  # 完整技術文檔
```

## 安裝依賴

```bash
pip install -r ai_transcriber_gui/requirements.txt
```

**主要依賴**：- soundcard, soundfile
- openai-whisper, faster-whisper
- torch (CUDA 或 CPU 版本)
- pydub, numpy
- tkinter (Python 內建)

## 文檔

- **[project.md](project.md)** - 完整技術文檔（架構、流程、設計決策）
- **[PACKAGING.md](PACKAGING.md)** - 打包部署指南（詳細步驟、測試清單）
- **[.github/issue.md](.github/issue.md)** - 問題追蹤與修正記錄
- **[.github/copilot-instructions.md](.github/copilot-instructions.md)** - 開發指引

## 使用說明

### 錄音模式

1. 選擇「錄音來源」(麥克風/系統音)
2. 選擇「語言模式」(主要中文/主要英文/系統自動判斷)
3. 勾選「即時轉錄」(邊錄邊轉) 或不勾選 (錄完再轉)
4. 點擊「開始錄音」
5. 點擊「開始錄音」(再次) 停止錄音
6. 轉錄結果顯示在「轉錄結果」視窗，並自動存檔至 `exports/`

### 選檔案模式

1. 點擊「選取檔案」選擇音訊/影片檔案
2. 勾選「即時轉錄」(分段處理) 或不勾選 (整檔處理)
3. 等待轉錄完成
4. 結果顯示在「轉錄結果」視窗，並自動存檔至 `exports/`

### 清除功能

點擊「清除」按鈕可清空「轉錄結果」視窗，方便開始新的轉錄任務。

## 常見問題

**Q: 系統音錄不到聲音？**  
A: 確認已選擇正確的 loopback 裝置 (通常顯示為「喇叭 (loopback)」)。

**Q: 轉錄結果語言錯誤？**  
A: 選擇正確的「語言模式」：純中文選「主要中文」，純英文選「主要英文」。

**Q: 即時轉錄延遲多久？**  
A: 約 2.5 秒延遲（累積音訊後才轉錄，確保品質）。

**Q: 打包後 exe 找不到模型？**  
A: 確保 `model/` 資料夾放置於 exe 同層目錄。詳見 [PACKAGING.md](PACKAGING.md)。

## 技術特點

- **單一音源設計**：避免混音複雜度，專注品質
- **即時轉錄優化**：累積 2.5 秒音訊緩衝，平衡延遲與準確度
- **Prompt 過濾**：自動過濾 Whisper 輸出的 prompt 內容
- **Thread 安全**：Queue-based 架構，避免 UI 凍結
- **路徑自適應**：打包後自動使用 exe-relative 路徑

## 授權

MIT License

## 貢獻

歡迎提交 Issue 或 Pull Request。

---

**環境需求**：Windows 10/11, Python 3.10+, CUDA 11.8+ (選用)  
**測試環境**：Windows 11, Python 3.12, CUDA 12.1
```

功能要點
- 錄製麥克風並轉存 MP3（存於 `recordings/`）。
- 選取影音檔（mp4/mkv/mp3 等）後自動擷取音訊並轉錄。
- 提供語言模式選擇（主要中文 / 主要英文 / 系統自動判斷）。
- 轉錄結果會顯示在 GUI 並可匯出到 `exports/`。

依賴與安裝注意
- 若使用 CPU-only PyTorch（Windows），請參考官方安裝頁面選擇適合的 wheel，或用範例命令：

```bash
pip install --index-url https://download.pytorch.org/whl/cpu torch
```

- 欲使用 GPU/CUDA，請到 PyTorch 官網選取對應 CUDA 版本的安裝指令。

- 若要啟用拖放功能，安裝 `tkinterdnd2`（已在 requirements.txt 中標示為選用）。

打包成可執行檔（選用）
- 專案根目錄包含 `build_exe.py`，其會依需求打包 `ai_transcriber_gui/main.py` 與 `ffmpeg` 等必要資源。
- 建議不要把模型、exports、recordings 打包進 exe；改為放於同一層資料夾供 exe 存取。

常見問題
- 下載模型時需要大量空間與時間（首次運行會下載）。
- 若 GUI 在轉錄時卡頓，確認應用是否使用 `threading`（程式已採用）且機器資源是否足夠；可考慮改用較小的模型（`small` 或 `base`）。

貢獻與授權
- 若要修改程式或提交 PR，請在本地測試變更並確保不將大型模型檔加入版本控制。

---
最後更新：2026-04-09

WASAPI Loopback (系統音) 支援與測試
----------------------------------

本程式已新增對 Windows WASAPI loopback（系統播放音訊）錄製的支援，會嘗試以下列順序擷取系統音：

- 優先使用 PyAudio（建議使用已打補丁支援 WASAPI loopback 的 PortAudio wheel，例如 `PyAudioWPatch`）。
- 若 PyAudio 不可用，會嘗試透過 `soundcard` 列舉的 loopback 類型麥克風（若有）作為替代。

安裝建議（conda env 範例）：

```powershell
conda activate lang_learn
pip install -r ai_transcriber_gui/requirements.txt
# 若需要可靠的 WASAPI loopback，安裝 PyAudioWPatch（示例版號，請以最新為準）
pip install PyAudioWPatch==0.2.12.8
```

啟動與測試

1. 用你安裝了 PyAudioWPatch 的 Python 啟動應用程式：

```powershell
D:\conda_envs\lang_learn\python ai_transcriber_gui\main.py
```

2. 在 GUI 中選擇錄音來源為「雙軌 (Mic + Loopback)」，按下錄製並在電腦播放一段系統聲音（或會議音），錄製 8–10 秒後停止。
3. 觀察左下角兩個 VU 表：`m` 為麥克風，`s` 為系統/loopback。若 `s` 有波動代表已捕捉到系統音。
4. 完成後檢查 `ai_transcriber_gui/recordings/` 是否產生 `loop_*.mp3`（或 wav），以及 `ai_transcriber_gui/exports/transcriber.log` 以取得診斷資訊。

疑難排解

- 若 GUI 只錄到麥克風但沒有系統音：
	- 確認 GUI 是使用你已安裝 PyAudioWPatch 的 Python（`sys.executable` 與你執行安裝時一致）。
	- 若沒有 PyAudioWPatch，可執行專用裝置列舉腳本 `ai_transcriber_gui/list_devices.py`，檢查是否有 Loopback 類型的麥克風（例如 `Loopback 喇叭 (Realtek...)`）。
	- 若 `list_devices.py` 顯示有 loopback，但程式仍未捕捉，請將 `ai_transcriber_gui/exports/transcriber.log` 與裝置列舉輸出貼上以便分析。

- 若出現大量 "data discontinuity" 或 MediaFoundation 相關警告：
	- 程式已嘗試調高 chunk 大小並使用裝置原生取樣率以減少此問題；若問題仍存在，建議改用 PyAudioWPatch 路徑或更新音效驅動程式。

文件更新紀錄
- 2026-04-12: 新增 WASAPI loopback 測試說明與 PyAudioWPatch 建議安裝步驟。
