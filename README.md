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
