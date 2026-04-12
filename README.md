# AI 會議錄音轉文字（GUI）

簡短說明
- 本專案提供一個基於 tkinter 的桌面 GUI，用於錄製或選取本機影音檔，並使用地端 Whisper / faster-whisper 模型進行中英夾雜優化的語音轉文字（STT）。

目錄
- `ai_transcriber_gui/`：主程式與資源。
- `ai_transcriber_gui/ffmpeg/`：可放置 ffmpeg 可執行檔（選用，或將 ffmpeg 加入系統 PATH）。
- `ai_transcriber_gui/model/`：放置本地模型權重（請勿將大型檔案加入版本控制）。
- `ai_transcriber_gui/recordings/`：錄音 MP3 存放（已被 .gitignore 忽略）。
- `ai_transcriber_gui/exports/`：轉錄輸出（已被 .gitignore 忽略）。

快速開始
1. 建議建立並啟用虛擬環境（venv 或 conda）。
2. 安裝依賴：

```bash
pip install -r ai_transcriber_gui/requirements.txt
```

3. 確認 FFmpeg：
- 可將 `ffmpeg/bin/ffmpeg.exe` 放在 `ai_transcriber_gui/ffmpeg/bin/`，或把系統上的 ffmpeg 加到 PATH。若無 ffmpeg，部分媒體檔（例如 mp4/mkv 提取音訊）可能無法處理。

4. 放置模型（可選）：
- 將 Whisper 或 faster-whisper 的模型權重放入 `ai_transcriber_gui/model/`，例如 `ai_transcriber_gui/model/whisper/` 或 `ai_transcriber_gui/model/faster-whisper/`。權重通常很大，請勿加入 git 版本控制。

執行

```bash
python ai_transcriber_gui/main.py
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
