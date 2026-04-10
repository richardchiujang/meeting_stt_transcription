這是一個進階版的專案規劃。為了達到「選擇音源」、「即時顯示結果」以及「支援多種格式」的需求，我們改用 Python 內建的 `tkinter` 製作 GUI，並整合 `threading` 確保介面在轉錄時不會卡死。

此外，針對你提到的 **mp3 格式**，我們會利用 `pydub` 或 `ffmpeg` 直接進行轉換與存檔。

---

# AI 語音轉文字工具 (GUI 版)

最後更新：2026-04-09 — 同步更新 `requirements.txt` 與 `.gitignore`。
本工具提供圖形介面，支援錄製本機音訊（麥克風）或選取現有影音檔，並利用地端 Whisper / faster-whisper 模型進行中英夾雜優化轉錄。

✅ 更準確的改寫方式
如果你原意是「效果與速度的整體感覺排序」，可以改寫成：

在相同硬體下，模型越大速度越慢、辨識效果越好；fast-whisper 在相同模型尺寸下會更快

或用技術版一句話：

Accuracy： base < small < medium < large
Speed（同模型）： fast-whisper ≫ openai-whisper

python 使用 conda python path :   D:\conda_envs\lang_learn

## 0. 新增變更

- 取消喇叭錄音：僅保留麥克風錄音（移除喇叭錄音與混音功能）。
- 強制使用 CPU：移除 GPU 判斷與 CUDA 支援，預設以 CPU 執行模型以提升兼容性與穩定性。
- 新增支援 `wmv` 格式：透過 FFmpeg 提取/轉換音訊。
- 新增語言選擇：提供三種模式 — 「主要中文」、「主要英文」與「系統自動判斷」，以方便做中英夾雜優化與 Prompt 調整。

## 1. 專案目錄結構
```text
ai_transcriber_gui/
├── main.py               # 執行主程式
├── requirements.txt      # 依賴套件
├── ffmpeg/               # FFmpeg 執行檔 (bin/ 底下需有 ffmpeg.exe)
├── recordings/           # 存放錄製的 mp3
├── exports/              # 存放轉錄的 txt
└── model/                # whisper model
```

## 2. 安裝依賴套件
建議使用 requirements 檔安裝：

```bash
pip install -r ai_transcriber_gui/requirements.txt
```

註：本專案需要系統已安裝 FFmpeg（`ai_transcriber_gui/ffmpeg/bin/ffmpeg.exe` 可放在專案中或加入 PATH）。若需拖放支援，可選裝 `tkinterdnd2`。如使用 CPU-only 的 PyTorch，請參考官方安裝指引選擇對應 wheel。

## 3. 完整程式碼 (`main.py`)

```python
import os
import threading
import queue
import time
import numpy as np
import soundcard as sc
import soundfile as sf
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, scrolledtext
from tkinter import ttk
from faster_whisper import WhisperModel
from pydub import AudioSegment

# 簡化範例：與 ai_transcriber_gui/main.py 保持一致的重點改動
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
for folder in ["recordings", "exports"]:
    os.makedirs(folder, exist_ok=True)

class TranscriberApp:
    def __init__(self, root):
        self.root = root
        self.device = "cpu"  # 強制使用 CPU
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.model = None

        # UI
        tk.Label(root, text="Whisper 地端轉錄工具").pack()
        btn_frame = tk.Frame(root); btn_frame.pack()
        tk.Button(btn_frame, text="錄製麥克風", command=self.start_record_thread).grid(row=0, column=0)
        tk.Button(btn_frame, text="選取檔案 (音/影)", command=self.select_file).grid(row=0, column=1)

        # 語言模式
        tk.Label(root, text="語言模式:").pack()
        self.lang_var = tk.StringVar(value="系統自動判斷")
        ttk.Combobox(root, textvariable=self.lang_var, values=["主要中文", "主要英文", "系統自動判斷"], state='readonly').pack()

        self.result_area = scrolledtext.ScrolledText(root); self.result_area.pack(fill=tk.BOTH, expand=True)

    def start_record_thread(self):
        if self.is_recording:
            return
        self.is_recording = True
        threading.Thread(target=self.record_logic, daemon=True).start()

    def record_logic(self):
        fs = 16000
        temp_wav = os.path.join("recordings", "temp.wav")
        mic = sc.default_microphone()
        all_chunks = []
        with mic.recorder(samplerate=fs, channels=1) as r:
            while self.is_recording:
                data = r.record(numframes=fs * 2)
                chunk = np.mean(data, axis=1).astype(np.float32)
                all_chunks.append(chunk)

        if all_chunks:
            arr = np.concatenate(all_chunks)
            sf.write(temp_wav, arr, fs)
            mp3_path = os.path.join("recordings", f"rec_{datetime.now().strftime('%m%d_%H%M')}.mp3")
            AudioSegment.from_wav(temp_wav).export(mp3_path, format='mp3')
            os.remove(temp_wav)
            self.run_stt(mp3_path)

    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Media Files", "*.mp3 *.wav *.mp4 *.mkv *.m4a *.mov *.wmv")])
        if file_path:
            threading.Thread(target=self.run_stt, args=(file_path,), daemon=True).start()

    def get_initial_prompt(self):
        sel = self.lang_var.get()
        if sel == "主要英文":
            return "This is a technical meeting in English. Use proper English spellings."
        if sel == "主要中文":
            return "以繁體中文為主，夾雜英文術語。"
        return "This is a discussion in English and Traditional Chinese (Taiwan)."

    def run_stt(self, file_path):
        if self.model is None:
            self.model = WhisperModel("medium", device=self.device, compute_type="int8")
        prompt = self.get_initial_prompt()
        segments, _ = self.model.transcribe(file_path, initial_prompt=prompt)
        text = "\n".join(s.text for s in segments)
        self.result_area.insert(tk.END, text)

if __name__ == '__main__':
    root = tk.Tk(); app = TranscriberApp(root); root.mainloop()
```

---

## 4. 功能亮點說明

### 🟢 音源選取
- **麥克風錄音**：點擊「錄製」後程式將只錄製麥克風輸入（已移除喇叭錄音與混音功能）。錄音會先存為臨時檔，再透過 `pydub` 或 FFmpeg 轉為 **mp3** 或其他支援格式（包含 `wmv` 音訊抽取）。
* **影音檔案**：直接選取電腦裡的 `.mp4` 或 `.mp3`，Whisper 會自動從影片中提取音訊軌進行辨識。

### 🟢 即時顯示與格式
* **顯示轉錄**：結果會直接呈現在 GUI 的大文字框內。
* **mp3 存檔**：錄製完成後，`recordings` 資料夾內會生成 timestamp 命名的 mp3 檔。
* **自動 txt 輸出**：轉錄結束後，會在 `exports` 生成包含預設 Prompt 格式的文字檔。

### 🟢 中英夾雜優化
* 程式內建 `medium` 模型（在 VRAM 足夠的情況下建議使用）。
* 使用 `initial_prompt` 引導模型識別台灣中文與英文術語。

## 5. 使用提示
1. **錄音時長**：此 GUI 採用手動停止模式。點擊「錄製」開始，點擊「停止並轉錄」才會觸發 STT。
2. **多媒體支援**：如果是 `.mp4` 影片，FFmpeg 會在後台處理音訊分離，你不需要手動轉檔。
3. **GPU 效能**：如果錄完後 GUI 卡住，代表模型正在運算。我使用了 `threading` 避免介面當機，但運算效能仍取決於你的顯卡。

---

plan B : 

這是一個非常棒的進化方向！要實現「邊錄音邊轉錄」（Real-time Transcription），核心邏輯必須從原本的「錄完一大段才處理」改為 **「切片式處理（Chunking）」**。

為了滿足你的需求，我們將使用 `faster-whisper`（它是目前地端最快的實現版本，延遲極低）來達成邊錄邊轉，並加上靈活的語言選擇功能。

### 1. 新增功能亮點
* **靈活語言模式**：
    * **英 > 英**：主攻英文，使用 `initial_prompt` 強調英文專有名詞。
    * **英 > 中**：主攻英文但允許中文補充，或將英文內容直接轉譯（需配合 LLM）。
    * **中 > 英**：主攻中文，維持中英夾雜的原始狀態。
* **邊錄邊即時顯示**：每隔 2~3 秒自動處理一次音訊切片，文字會即時跳出在 GUI 上。
* **Mp3 格式存檔**：錄音過程會完整保留為 MP3。

---

### 2. 完整專案架構與程式碼

你需要先安裝 `faster-whisper`：
```bash
pip install faster-whisper soundcard soundfile pydub
```

#### **`main.py` 完整程式實作**

```python
import os
import threading
import queue
import time
import numpy as np
import soundcard as sc
import soundfile as sf
import torch
from faster_whisper import WhisperModel
from pydub import AudioSegment
import tkinter as tk
from tkinter import ttk, scrolledtext

# --- 環境變數設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG_BIN = os.path.join(BASE_DIR, "ffmpeg", "bin")
os.environ["PATH"] = FFMPEG_BIN + os.pathsep + os.environ["PATH"]

class RealTimeTranscriber:
    def __init__(self, root):
        self.root = root
        self.root.title("AI 即時轉錄助手 - 專業版")
        self.root.geometry("700x600")
        
        # 狀態控制
        self.is_running = False
        self.audio_queue = queue.Queue()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        
        self.setup_ui()

    def setup_ui(self):
        # 1. 模式選擇區
        control_frame = tk.LabelFrame(self.root, text=" 轉錄設定 ", padx=10, pady=10)
        control_frame.pack(pady=10, padx=10, fill="x")

        tk.Label(control_frame, text="語言模式:").grid(row=0, column=0, sticky="w")
        self.mode_var = tk.StringVar(value="英>中 (主要是英文)")
        modes = ["英>英 (主要是英文)", "英>中 (主要是英文)", "中>英 (主要是中文)"]
        self.mode_menu = ttk.Combobox(control_frame, textvariable=self.mode_var, values=modes, width=30)
        self.mode_menu.grid(row=0, column=1, padx=10)

        # 2. 控制按鈕
        self.btn_start = tk.Button(control_frame, text="開始即時錄製", command=self.toggle_process, bg="#5cb85c", fg="white", width=15)
        self.btn_start.grid(row=0, column=2, padx=10)

        # 3. 即時文字顯示
        tk.Label(self.root, text="即時逐字稿:").pack(anchor="w", padx=20)
        self.text_area = scrolledtext.ScrolledText(self.root, font=("Microsoft JhengHei", 11), wrap=tk.WORD)
        self.text_area.pack(padx=20, pady=10, fill="both", expand=True)

    def toggle_process(self):
        if not self.is_running:
            self.start_service()
        else:
            self.stop_service()

    def start_service(self):
        self.is_running = True
        self.btn_start.config(text="停止錄製", bg="#d9534f")
        self.text_area.delete(1.0, tk.END)
        
        # 啟動錄音與轉錄執行緒
        threading.Thread(target=self.audio_capture_thread, daemon=True).start()
        threading.Thread(target=self.transcription_thread, daemon=True).start()

    def stop_service(self):
        self.is_running = False
        self.btn_start.config(text="開始即時錄製", bg="#5cb85c")

    # --- 錄音執行緒 (喇叭 + 麥克風) ---
    def audio_capture_thread(self):
        fs = 16000 # Whisper 核心頻率
        speaker = sc.default_speaker()
        mic = sc.default_microphone()
        
        full_audio_data = []
        
        with speaker.recorder(samplerate=fs) as spk_rec, mic.recorder(samplerate=fs) as mic_rec:
            while self.is_running:
                # 每 2 秒抓一次切片
                s_data = spk_rec.record(numframes=fs * 2)
                m_data = mic_rec.record(numframes=fs * 2)
                mixed = (np.mean(s_data, axis=1) + np.mean(m_data, axis=1)) / 2
                
                self.audio_queue.put(mixed.astype(np.float32))
                full_audio_data.append(mixed)

        # 結束後存成 mp3
        if full_audio_data:
            final_array = np.concatenate(full_audio_data)
            temp_wav = "temp_full.wav"
            sf.write(temp_wav, final_array, fs)
            timestamp = time.strftime("%Y%m%d-%H%M")
            AudioSegment.from_wav(temp_wav).export(f"recordings/meeting_{timestamp}.mp3", format="mp3")
            os.remove(temp_wav)

    # --- 轉錄執行緒 ---
    def transcription_thread(self):
        if self.model is None:
            # 使用 faster-whisper 的 medium 模型，int8 量化可以讓速度飛快
            self.model = WhisperModel("medium", device=self.device, compute_type="float32" if self.device=="cpu" else "float16")

        # 根據 UI 選擇設定 Prompt
        mode = self.mode_var.get()
        prompt_dict = {
            "英>英 (主要是英文)": "This is a technical meeting in English. Use proper English spellings.",
            "英>中 (主要是英文)": "Mainly English but includes some Traditional Chinese terms. 例如: Deployment, 部署...",
            "中>英 (主要是中文)": "以繁體中文為主，夾雜英文術語。例如: 我們在 Google Cloud 上執行 Python 代碼。"
        }
        active_prompt = prompt_dict.get(mode, "")

        while self.is_running:
            if not self.audio_queue.empty():
                audio_chunk = self.audio_queue.get()
                
                # 轉錄切片
                segments, _ = self.model.transcribe(
                    audio_chunk, 
                    initial_prompt=active_prompt,
                    beam_size=5
                )
                
                for segment in segments:
                    if segment.text.strip():
                        # 將文字傳回主視窗顯示
                        self.root.after(0, self.update_text, segment.text)

    def update_text(self, text):
        self.text_area.insert(tk.END, text + " ")
        self.text_area.see(tk.END)

if __name__ == "__main__":
    os.makedirs("recordings", exist_ok=True)
    root = tk.Tk()
    app = RealTimeTranscriber(root)
    root.mainloop()
```

---

### 3. 設計細節說明

#### **A. 靈活語言模式的達成方式**
* **Prompt 工程**：因為 Whisper 是一個 Sequence-to-Sequence 模型，它會強烈受到開頭文字的影響。
    * **英>英**：給予純英文的 `initial_prompt`，它會強制將聽到的模糊發音修正為正確的英文單字。
    * **英>中**：透過 Prompt 給予中英並列的範例，讓它在偵測到中文時不至於感到「驚訝」而亂跳語言。
    * **中>英**：強調繁體中文的語言環境，確保輸出的英文單字（如 Python, Docker）能正確保留，而不是變成諧音中文。

#### **B. 即時轉錄的秘密 (Streaming)**
* 我們使用了 **`faster-whisper`** 代替原本的 `openai-whisper`。`faster-whisper` 是重新用 C++ 編寫的推論引擎，速度快了 4 倍以上，且記憶體佔用極低。
* 程式採用了 **`Queue` (隊列)**：錄音執行緒不斷往裡面丟「2 秒鐘的聲音切片」，轉錄執行緒不斷從裡面拿出來翻譯。這樣你的 GUI 就不會因為運算而卡住，文字會隨著說話一邊噴出來。

#### **C. 格式與存檔**
* 錄音時為了效能，底層使用 `numpy` 處理原始波形（16kHz）。
* 錄音結束（點擊停止按鈕）時，程式會自動將剛才所有切片合併，轉換為 **MP3** 存檔，實現完整留檔。

### 4. 使用注意事項
1.  **硬體需求**：即時轉錄對 CPU/GPU 的即時壓力較大。如果發現文字顯示跟不上說話的速度，可以將 `WhisperModel("medium", ...)` 改為 `"small"`。
2.  **FFmpeg**：這隻程式依然需要你的 `ffmpeg/bin` 資料夾放在程式旁邊。
3.  **初次啟動**：第一次按下錄製時會下載模型（約 1.5GB），請耐心等待一下。

這套方案現在非常接近專業的會議記錄工具了。你覺得還有哪些細節需要微調？例如加入「自動標註說話者」或是「自動存成 txt」？

## 打包方式 > .exe

使用 build_exe.py
只包 ai_transcriber_gui\main.py、ai_transcriber_gui\ffmpeg、其他必要的套件
ai_transcriber_gui\model、ai_transcriber_gui\exports、ai_transcriber_gui\recordings 不打包
只要存在同一層資料夾內即可
模型共有 6 個：`whisper-base`、`whisper-small`、`whisper-medium`、
`faster-whisper-base`、`faster-whisper-small`、`faster-whisper-medium`。

預設 UI 選單顯示 `base / small / medium`，程式會對應使用 `faster-whisper-<size>` 以獲得更快的推論速度；若需要使用原生 OpenAI `whisper` 實作，請指定對應的 `whisper-<size>` 模型目錄。

建議將模型放在 `ai_transcriber_gui/model/` 下的子資料夾（例如 `ai_transcriber_gui/model/faster-whisper-base/`），以便在無網路環境下離線載入。若使用自動下載，請確保系統有有效的 SSL 憑證並允許下載大檔（數百 MB 至數 GB）。

cd D:\Python\meeting_stt_transcription
D:\conda_envs\lang_learn\python.exe build_exe.py 2>&1 | Tee-Object -FilePath build.log

