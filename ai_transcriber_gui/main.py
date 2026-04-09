import os
import threading
import queue
import time
import numpy as np
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from tkinter import ttk
import logging
import traceback

try:
    import soundcard as sc
    import soundfile as sf
except Exception:
    sc = None

try:
    import whisper
except Exception:
    whisper = None

try:
    from faster_whisper import WhisperModel as FWWhisperModel
except Exception:
    FWWhisperModel = None

try:
    from pydub import AudioSegment
except Exception:
    AudioSegment = None

try:
    import torch
except Exception:
    torch = None


# Setup folders and FFmpeg path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG_BIN = os.path.join(BASE_DIR, "ffmpeg", "bin")
FFMPEG_EXE = os.path.join(FFMPEG_BIN, "ffmpeg.exe")
if os.path.isdir(FFMPEG_BIN):
    os.environ["PATH"] = FFMPEG_BIN + os.pathsep + os.environ.get("PATH", "")

# Explicitly set FFmpeg executable for pydub so it uses the bundled binary
if AudioSegment is not None and os.path.isfile(FFMPEG_EXE):
    AudioSegment.converter = FFMPEG_EXE

# Default local model directories (no network download needed)
DEFAULT_FW_MODEL = os.path.join(BASE_DIR, "model", "faster-whisper")
DEFAULT_W_MODEL_DIR = os.path.join(BASE_DIR, "model", "whisper")

for folder in ["recordings", "exports"]:
    os.makedirs(folder, exist_ok=True)

# Setup logging to file and console
log_path = os.path.join("exports", "transcriber.log")
logger = logging.getLogger("transcriber")
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(log_path, encoding="utf-8", mode="w")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
file_handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


class TranscriberApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI 語音轉文字助手")
        self.root.geometry("780x600")

        # force CPU-only per project.md changes
        self.device = "cpu"

        # recording and transcription state
        self.is_recording = False
        self.full_audio = []
        self._record_fs = 16000
        self.model = None
        self.fw_model = None
        self.loaded_model_name = None
        self.audio_queue = queue.Queue()
        self.transcribe_thread = None
        self.stop_transcription = False

        self.setup_ui()

    def setup_ui(self):
        tk.Label(self.root, text="Whisper 地端轉錄工具", font=("Arial", 14, "bold")).pack(pady=8)
        self.status_label = tk.Label(self.root, text=f"硬體加速: {self.device.upper()}", fg="blue")
        self.status_label.pack()

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=8)

        self.btn_record = tk.Button(btn_frame, text="錄製麥克風", command=self.start_record_thread, bg="#f0ad4e")
        self.btn_record.grid(row=0, column=0, padx=6)
        self.btn_stop = tk.Button(btn_frame, text="停止錄音並轉錄", command=self.stop_record, bg="#d9534f", fg="white")
        self.btn_stop.grid(row=0, column=1, padx=6)
        tk.Button(btn_frame, text="選取檔案 (音/影)", command=self.select_file, bg="#5bc0de").grid(row=0, column=2, padx=6)

        # Real-time option and stop-transcription button
        self.realtime_var = tk.BooleanVar(value=False)
        tk.Checkbutton(btn_frame, text="即時 (chunked) 轉錄", variable=self.realtime_var).grid(row=0, column=3, padx=8)
        # toggle watcher will enable/disable stop-record button
        self.realtime_var.trace_add("write", self._on_realtime_change)
        self.btn_stop_trans = tk.Button(btn_frame, text="停止轉錄", command=self.stop_transcription_now, bg="#ff6f61")
        self.btn_stop_trans.grid(row=0, column=4, padx=6)

        # Model selection dropdown
        model_frame = tk.Frame(self.root)
        model_frame.pack(pady=(6, 0), padx=8, fill=tk.X)
        tk.Label(model_frame, text="模型:").pack(side=tk.LEFT)
        available_models = self._scan_models()
        default_model = "base" if "base" in available_models else available_models[0]
        self.model_var = tk.StringVar(value=default_model)
        self.model_combo = ttk.Combobox(
            model_frame, textvariable=self.model_var,
            values=available_models, state="readonly", width=20
        )
        self.model_combo.pack(side=tk.LEFT, padx=6)
        self.model_var.trace_add("write", self._on_model_change)

        # Language selection placed to the right of model selector
        tk.Label(model_frame, text="語言模式:").pack(side=tk.LEFT, padx=(12, 0))
        self.lang_var = tk.StringVar(value="系統自動判斷")
        lang_options = ["主要中文", "主要英文", "系統自動判斷"]
        self.lang_combo = ttk.Combobox(model_frame, textvariable=self.lang_var, values=lang_options, state="readonly", width=20)
        self.lang_combo.pack(side=tk.LEFT, padx=6)

        tk.Label(self.root, text="轉錄結果:").pack(anchor="w", padx=18)
        self.result_area = scrolledtext.ScrolledText(self.root, height=24, wrap=tk.WORD)
        self.result_area.pack(padx=18, pady=6, fill=tk.BOTH, expand=True)

        # Progress bar at bottom
        progress_frame = tk.Frame(self.root)
        progress_frame.pack(fill=tk.X, padx=12, pady=(0,12))
        tk.Label(progress_frame, text="狀態:").pack(side=tk.LEFT)
        self.progress = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.progress_label = tk.Label(progress_frame, text="0%")
        self.progress_label.pack(side=tk.LEFT, padx=(6,0))

    def log(self, text):
        ts = datetime.now().strftime('%H:%M:%S')
        line = f"[{ts}] {text}\n"
        self.result_area.insert(tk.END, line)
        self.result_area.see(tk.END)
        logger.info(text)

    def start_record_thread(self):
        if self.is_recording:
            return
        if sc is None:
            messagebox.showerror("缺少套件", "soundcard/soundfile 未安裝，無法錄音。請安裝 requirements.txt 中的套件。")
            return

        self.is_recording = True
        # reset buffer for this recording session
        self.full_audio = []
        self._record_fs = 16000 if self.realtime_var.get() else 48000
        self.stop_transcription = False
        self.log("開始錄音 (麥克風)...")

        # start transcription thread when realtime enabled
        if self.realtime_var.get():
            self.transcribe_thread = threading.Thread(target=self.transcription_worker, daemon=True)
            self.transcribe_thread.start()

        threading.Thread(target=self.record_logic, daemon=True).start()

    def record_logic(self):
        fs = self._record_fs
        temp_wav = os.path.join("recordings", "temp.wav")

        try:
            mic = sc.default_microphone()

            with mic.recorder(samplerate=fs, channels=1) as mic_rec:
                while self.is_recording:
                    frames = fs * 2 if self.realtime_var.get() else fs // 2
                    m_data = mic_rec.record(numframes=frames)

                    chunk = np.mean(m_data, axis=1).astype(np.float32)
                    # append to shared buffer for possible early save
                    try:
                        self.full_audio.append(chunk)
                    except Exception:
                        pass

                    if self.realtime_var.get():
                        try:
                            self.audio_queue.put(chunk, block=False)
                        except Exception:
                            pass

            if not self.full_audio:
                self.log("錄音沒有捕捉到資料。")
                return

            final_array = np.concatenate(self.full_audio) if self.full_audio else np.array([], dtype=np.float32)
            sf.write(temp_wav, final_array, fs)

            ts = datetime.now().strftime('%m%d_%H%M')
            mp3_path = os.path.join("recordings", f"rec_{ts}.mp3")

            if AudioSegment is not None:
                AudioSegment.from_wav(temp_wav).export(mp3_path, format="mp3")
                os.remove(temp_wav)
            else:
                mp3_path = temp_wav

            self.log(f"錄音結束，已存為 {mp3_path}")

            if self.realtime_var.get():
                self.audio_queue.put(None)
            else:
                self.run_stt(mp3_path)

        except Exception as e:
            self.log(f"錄音錯誤: {e}")

    def stop_record(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.log("停止錄音，處理中...")

    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Media Files", "*.mp3 *.wav *.mp4 *.mkv *.m4a *.mov *.wmv")])
        if file_path:
            self.log(f"選取檔案: {os.path.basename(file_path)}")
            # file transcription runs in background
            threading.Thread(target=self.run_stt, args=(file_path,), daemon=True).start()

    def start_progress(self):
        try:
            # indeterminate by default; start animation
            self.progress.config(mode='indeterminate')
            self.progress.start(10)
            self.update_progress_label(0)
        except Exception:
            pass

    def stop_progress(self):
        try:
            self.progress.stop()
            # reset label
            self.update_progress_label(0)
        except Exception:
            pass

    def update_progress_label(self, percent: int):
        try:
            pct = int(percent)
        except Exception:
            pct = 0
        self.progress_label.config(text=f"{pct}%")

    def stop_transcription_now(self):
        self.stop_transcription = True
        # clear queue
        try:
            while not self.audio_queue.empty():
                self.audio_queue.get_nowait()
        except Exception:
            pass
        self.stop_progress()
        self.log("使用者已停止轉錄。")
        logger.info("User requested stop_transcription_now")
        self._save_partial_result()
        # save any audio captured so far (realtime or not)
        try:
            self._save_recording_file()
        except Exception:
            logger.exception("Failed to save recording on stop_transcription_now")

    def _save_partial_result(self):
        """Write whatever STT text is currently in the result area to an output file."""
        try:
            raw = self.result_area.get("1.0", tk.END).strip()
            if not raw:
                return
            MEETING_PROMPT = (
                "你是一個會議助理，請將以下會議逐字稿（STT，自動語音轉文字，可能包含口語、錯字或重複內容）"
                "重整為一份專業的會議摘要文件。\n\n"
                "輸出請遵循以下格式與原則：\n\n"
                "【輸出格式】\n"
                "- 會議主題：\n"
                "- 議題摘要（條列）：\n"
                "- 討論項目摘要：\n"
                "- 代辦事項（Action Items）：\n"
                "- 結論事項：\n\n"
                "【整理原則】\n"
                "- 不要逐字翻寫逐字稿，請進行語意理解與摘要\n"
                "- 合併重複內容，移除寒暄與非討論性語句\n"
                "- 若未明確提及負責人，可僅列代辦事項內容\n"
                "- 全文使用繁體中文，條列清楚、結構明確\n\n"
                "---\n"
            )
            output_txt = os.path.join("exports", f"note_{datetime.now().strftime('%m%d_%H%M')}.txt")
            with open(output_txt, "w", encoding="utf-8") as f:
                f.write(f"{MEETING_PROMPT}\n{raw}")
            self.log(f"部分轉錄已存至: {output_txt}")
            logger.info("Partial result saved to %s", output_txt)
        except Exception as e:
            self.log(f"儲存部分轉錄失敗: {e}")
            logger.exception("_save_partial_result failed")

    def _save_recording_file(self):
        """Write current accumulated realtime recording to an mp3 (if any)."""
        try:
            if not getattr(self, 'full_audio', None):
                return None
            # create temp wav and export to mp3
            ts = datetime.now().strftime('%m%d_%H%M%S')
            tmp_wav = os.path.join('recordings', f'realtime_{ts}.wav')
            mp3_path = os.path.join('recordings', f'realtime_{ts}.mp3')
            try:
                arr = np.concatenate(self.full_audio)
            except Exception:
                return None
            sf.write(tmp_wav, arr, getattr(self, '_record_fs', 16000))
            if AudioSegment is not None:
                try:
                    AudioSegment.from_wav(tmp_wav).export(mp3_path, format='mp3')
                    os.remove(tmp_wav)
                except Exception:
                    # if export fails, keep wav
                    mp3_path = tmp_wav
            else:
                mp3_path = tmp_wav
            self.log(f"已儲存即時錄音檔: {mp3_path}")
            return mp3_path
        except Exception:
            logger.exception('_save_recording_file failed')
            return None

    def _on_realtime_change(self, *args):
        try:
            if self.realtime_var.get():
                # disable "停止錄音並轉錄" when realtime is enabled
                self.btn_stop.config(state=tk.DISABLED)
            else:
                self.btn_stop.config(state=tk.NORMAL)
        except Exception:
            pass

    def get_initial_prompt(self):
        """Return initial_prompt text according to language selection."""
        mode = getattr(self, 'lang_var', None)
        if mode is None:
            return "This is a discussion in English and Traditional Chinese (Taiwan)."
        sel = self.lang_var.get()
        if sel == "主要英文":
            return "This is a technical meeting in English. Use proper English spellings."
        if sel == "主要中文":
            return "以繁體中文為主，夾雜英文術語。"
        return "This is a discussion in English and Traditional Chinese (Taiwan)."

    def _scan_models(self):
        """Return list of available model names from model/ directory."""
        models = []
        if os.path.isdir(DEFAULT_W_MODEL_DIR):
            for f in sorted(os.listdir(DEFAULT_W_MODEL_DIR)):
                if f.endswith(".pt"):
                    models.append(os.path.splitext(f)[0])
        if os.path.isfile(os.path.join(DEFAULT_FW_MODEL, "model.bin")):
            models.append("faster-whisper")
        return models if models else ["base"]

    def _on_model_change(self, *_args):
        """Reset cached model when selection changes."""
        self.model = None
        self.fw_model = None
        self.loaded_model_name = None

    def cleanup_models(self):
        # delete model references and free GPU memory if possible
        try:
            if self.fw_model is not None:
                try:
                    del self.fw_model
                except Exception:
                    pass
                self.fw_model = None
            if self.model is not None:
                try:
                    del self.model
                except Exception:
                    pass
                self.model = None
            if torch is not None and hasattr(torch, 'cuda'):
                try:
                    torch.cuda.empty_cache()
                    logger.info('Called torch.cuda.empty_cache()')
                except Exception:
                    logger.exception('Failed to empty torch cuda cache')
        except Exception:
            logger.exception('cleanup_models error')

    def on_closing(self):
        # stop recording and transcription threads, cleanup models, then close
        self.log('關閉應用程式: 停止執行緒並釋放資源...')
        logger.info('Application closing requested')
        try:
            self.is_recording = False
            self.stop_transcription = True
            # clear queue
            try:
                while not self.audio_queue.empty():
                    self.audio_queue.get_nowait()
            except Exception:
                pass
            # give threads a moment to finish
            time.sleep(0.2)
        except Exception:
            logger.exception('Error while stopping threads')

        # cleanup models
        self.cleanup_models()

        # destroy GUI
        try:
            self.root.destroy()
        except Exception:
            pass

    def transcription_worker(self):
        # Real-time chunked transcription worker (live recording)
        if FWWhisperModel is None and whisper is None:
            self.log("未安裝 faster-whisper 或 openai-whisper，無法即時轉錄。")
            return

        selected = self.model_var.get()

        if selected == "faster-whisper":
            if FWWhisperModel is None:
                self.log("faster-whisper 未安裝，無法即時轉錄。")
                return
            if self.fw_model is None:
                try:
                    self.fw_model = FWWhisperModel(DEFAULT_FW_MODEL, device=self.device, compute_type="float16" if self.device=="cuda" else "int8")
                    self.log("已載入模型（即時模式）: faster-whisper")
                    logger.info("faster-whisper model loaded for realtime")
                except Exception as e:
                    self.fw_model = None
                    self.log(f"載入 faster-whisper 失敗: {e}")
                    logger.exception("Failed to load faster-whisper in transcription_worker")
                    return
        else:
            if whisper is None:
                self.log("openai-whisper 未安裝，無法即時轉錄。")
                return
            if self.model is None or self.loaded_model_name != selected:
                try:
                    self.log(f"已載入模型（即時模式）: {selected}")
                    self.model = whisper.load_model(selected, device=self.device, download_root=DEFAULT_W_MODEL_DIR)
                    self.loaded_model_name = selected
                except Exception as e:
                    self.log(f"載入 {selected} 失敗: {e}")
                    logger.exception("Failed to load whisper in transcription_worker")
                    return

        self.start_progress()

        while not self.stop_transcription:
            try:
                item = self.audio_queue.get(timeout=1.0)
            except Exception:
                # no data
                if not self.is_recording and self.audio_queue.empty():
                    break
                continue

            # None is completion marker
            if item is None:
                break

            # Transcribe chunk
            try:
                if selected == "faster-whisper" and self.fw_model is not None:
                    length = getattr(item, 'size', len(item) if item is not None else 0)
                    if length == 0:
                        continue
                    ip = self.get_initial_prompt()
                    segments, _ = self.fw_model.transcribe(item, initial_prompt=ip, beam_size=5)
                    for seg in segments:
                        txt = seg.text.strip()
                        if txt:
                            self.root.after(0, lambda t=txt: self.result_area.insert(tk.END, t + " "))
                            self.root.after(0, self.result_area.see, tk.END)
                elif self.model is not None:
                    # openai-whisper accepts float32 numpy array at 16 kHz
                    length = getattr(item, 'size', len(item) if item is not None else 0)
                    if length == 0:
                        continue
                    ip = self.get_initial_prompt()
                    res = self.model.transcribe(item, initial_prompt=ip, fp16=(self.device=="cuda"))
                    txt = res.get("text", "").strip()
                    if txt:
                        self.root.after(0, lambda t=txt: self.result_area.insert(tk.END, t + " "))
                        self.root.after(0, self.result_area.see, tk.END)

            except Exception as e:
                self.log(f"即時轉錄錯誤: {e}")
                logger.exception("Realtime transcription error")
        self.stop_progress()
        self.log("即時轉錄執行緒結束。")
        logger.info("transcription_worker finished")

    def run_stt(self, file_path):
        try:
            if FWWhisperModel is None and whisper is None:
                self.log("Whisper 套件未安裝，無法轉錄。")
                return
            self.start_progress()

            selected = self.model_var.get()
            use_realtime = self.realtime_var.get()

            # 即時模式 → 分段串流轉錄（依選單模型）
            if use_realtime:
                try:
                    self.log(f"開始分段轉錄 ({selected}, 可回報進度)...")
                    self.transcribe_file_stream(file_path)
                    return
                except Exception as e:
                    self.log(f"分段處理失敗: {e}，改為整檔轉錄。")
                    logger.exception("transcribe_file_stream failed")

            # 一般模式 → 依選單決定
            # Convert source to a reliable wav first (handles WMV/other containers)
            source = file_path
            tmp_src = None
            try:
                if AudioSegment is not None:
                    tmp_src = os.path.join("recordings", "convert_tmp.wav")
                    try:
                        AudioSegment.from_file(file_path).export(tmp_src, format="wav")
                        source = tmp_src
                    except Exception as e:
                        self.log(f"媒體轉換失敗，將嘗試直接使用原始檔案: {e}")
                        logger.exception('AudioSegment conversion failed')

            except Exception:
                tmp_src = None

            if selected == "faster-whisper":
                if FWWhisperModel is None:
                    self.log("faster-whisper 未安裝，無法轉錄。")
                    return
                if self.fw_model is None:
                    self.log("載入模型: faster-whisper")
                    self.fw_model = FWWhisperModel(
                        DEFAULT_FW_MODEL, device=self.device,
                        compute_type="float16" if self.device == "cuda" else "int8"
                    )
                    self.loaded_model_name = "faster-whisper"
                self.log("開始轉錄，請稍候...")
                ip = self.get_initial_prompt()
                # use converted source if available
                segments, _ = self.fw_model.transcribe(
                    source,
                    initial_prompt=ip
                )
                text = "\n".join(s.text for s in segments)
            else:
                if whisper is None:
                    self.log("openai-whisper 未安裝，無法轉錄。")
                    return
                if self.model is None or self.loaded_model_name != selected:
                    self.log(f"載入模型: {selected}")
                    self.model = whisper.load_model(
                        selected, device=self.device, download_root=DEFAULT_W_MODEL_DIR
                    )
                    self.loaded_model_name = selected
                self.log("開始轉錄，請稍候...")
                ip = self.get_initial_prompt()
                # use converted source if available
                try:
                    res = self.model.transcribe(
                        source,
                        initial_prompt=ip,
                        fp16=(self.device == "cuda")
                    )
                except Exception:
                    # fallback to original file if conversion produced invalid audio
                    logger.exception('transcribe failed on converted source, retrying original file')
                    res = self.model.transcribe(
                        file_path,
                        initial_prompt=ip,
                        fp16=(self.device == "cuda")
                    )
                text = res.get("text", "")
            self.root.after(0, lambda: self.result_area.insert(tk.END, f"\n--- 完成 ---\n{text}\n"))

            # clean up tmp conversion file
            try:
                if tmp_src is not None and os.path.isfile(tmp_src):
                    os.remove(tmp_src)
            except Exception:
                pass

            output_txt = os.path.join("exports", f"note_{datetime.now().strftime('%m%d_%H%M')}.txt")
            with open(output_txt, "w", encoding="utf-8") as f:
                MEETING_PROMPT = (
                    "你是一個會議助理，請將以下會議逐字稿（STT，自動語音轉文字，可能包含口語、錯字或重複內容）"
                    "重整為一份專業的會議摘要文件。\n\n"
                    "輸出請遵循以下格式與原則：\n\n"
                    "【輸出格式】\n"
                    "- 會議主題：\n"
                    "- 議題摘要（條列）：\n"
                    "- 討論項目摘要：\n"
                    "- 代辦事項（Action Items）：\n"
                    "- 結論事項：\n\n"
                    "【整理原則】\n"
                    "- 不要逐字翻寫逐字稿，請進行語意理解與摘要\n"
                    "- 合併重複內容，移除寒暄與非討論性語句\n"
                    "- 若未明確提及負責人，可僅列代辦事項內容\n"
                    "- 全文使用繁體中文，條列清楚、結構明確\n\n"
                    "---\n"
                )
                f.write(f"{MEETING_PROMPT}\nSource: {file_path}\n\n{text}")
            self.log(f"文字檔已存至: {output_txt}")

        except Exception as e:
            self.log(f"轉錄錯誤: {e}")
            logger.exception("run_stt failed")
        finally:
            self.stop_progress()

    def transcribe_file_stream(self, file_path, chunk_seconds=8):
        """Stream the input file in chunks and transcribe each chunk to report progress."""
        # ensure we have a wav temp file to read frames reliably
        tmp_wav = None
        try:
            # if pydub available, convert to wav for reliable reading
            if AudioSegment is not None:
                tmp_wav = os.path.join("recordings", "stream_tmp.wav")
                AudioSegment.from_file(file_path).export(tmp_wav, format="wav")
                source = tmp_wav
            else:
                source = file_path

            # open with soundfile for streaming
            with sf.SoundFile(source) as sfh:
                samplerate = sfh.samplerate
                total_frames = len(sfh)
                block_frames = int(samplerate * chunk_seconds)
                processed = 0
                parts = []

                # ensure model loaded based on dropdown selection
                selected = self.model_var.get()
                if selected == "faster-whisper":
                    if FWWhisperModel is None:
                        raise RuntimeError("faster-whisper 未安裝")
                    if self.fw_model is None:
                        self.fw_model = FWWhisperModel(DEFAULT_FW_MODEL, device=self.device, compute_type="float16" if self.device=="cuda" else "int8")
                        logger.info("faster-whisper model loaded for file stream")
                else:
                    if whisper is None:
                        raise RuntimeError("openai-whisper 未安裝")
                    if self.model is None or self.loaded_model_name != selected:
                        self.model = whisper.load_model(selected, device=self.device, download_root=DEFAULT_W_MODEL_DIR)
                        self.loaded_model_name = selected
                        logger.info("whisper model loaded for file stream: %s", selected)

                self.progress.config(mode='determinate', maximum=100)
                self.progress['value'] = 0
                self.update_progress_label(0)
                self.start_progress()

                while True:
                    data = sfh.read(frames=block_frames, dtype='float32')
                    if data is None or len(data) == 0:
                        break
                    parts.append(data)

                    # pre-process: convert to mono float32 at 16 kHz (faster-whisper requirement)
                    chunk = data
                    if chunk.ndim > 1:
                        chunk = chunk.mean(axis=1).astype(np.float32)
                    # skip empty chunks
                    if chunk is None or len(chunk) == 0:
                        continue
                    if samplerate != 16000:
                        num_out = int(round(len(chunk) * 16000 / samplerate))
                        if num_out <= 0:
                            continue
                        chunk = np.interp(
                            np.linspace(0, len(chunk), num_out, endpoint=False),
                            np.arange(len(chunk)),
                            chunk,
                        ).astype(np.float32)

                    # transcribe this chunk
                    try:
                        ip = self.get_initial_prompt()
                        if selected == "faster-whisper":
                            segments, _ = self.fw_model.transcribe(chunk, initial_prompt=ip)
                            for seg in segments:
                                txt = seg.text.strip()
                                if txt:
                                    self.root.after(0, lambda t=txt: self.result_area.insert(tk.END, t + " "))
                                    self.root.after(0, self.result_area.see, tk.END)
                        else:
                            res = self.model.transcribe(chunk, initial_prompt=ip, fp16=(self.device=="cuda"))
                            txt = res.get("text", "").strip()
                            if txt:
                                self.root.after(0, lambda t=txt: self.result_area.insert(tk.END, t + " "))
                                self.root.after(0, self.result_area.see, tk.END)
                    except Exception as e:
                        logger.exception("chunk transcribe failed")
                        self.log(f"分段轉錄錯誤: {e}")

                    processed += len(data)
                    percent = int(min(100, (processed / total_frames) * 100)) if total_frames > 0 else 0
                    # update progress bar and label
                    self.progress.config(mode='determinate')
                    self.progress['value'] = percent
                    self.update_progress_label(percent)

                    if self.stop_transcription:
                        logger.info("transcribe_file_stream stopped by user")
                        break

                # join parts for final text (optional) - we already printed segments
                self.stop_progress()
                self.log("分段轉錄完成。")

        finally:
            if tmp_wav is not None:
                try:
                    os.remove(tmp_wav)
                except Exception:
                    pass


def main():
    root = tk.Tk()
    app = TranscriberApp(root)
    # Ensure cleanup on window close
    try:
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
    except Exception:
        pass
    root.mainloop()


if __name__ == "__main__":
    main()
