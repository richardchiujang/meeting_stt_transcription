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
    import pyaudio as pa
    PA_AVAILABLE = True
except Exception:
    pa = None
    PA_AVAILABLE = False

# suppress known MediaFoundation runtime warning floods (data discontinuity)
try:
    import warnings
    from soundcard.mediafoundation import SoundcardRuntimeWarning
    warnings.filterwarnings('ignore', category=SoundcardRuntimeWarning)
except Exception:
    pass

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
PROJECT_ROOT = os.path.dirname(BASE_DIR)
FFMPEG_BIN = os.path.join(BASE_DIR, "ffmpeg", "bin")
FFMPEG_EXE = os.path.join(FFMPEG_BIN, "ffmpeg.exe")
if os.path.isdir(FFMPEG_BIN):
    os.environ["PATH"] = FFMPEG_BIN + os.pathsep + os.environ.get("PATH", "")

# Explicitly set FFmpeg executable for pydub so it uses the bundled binary
if AudioSegment is not None and os.path.isfile(FFMPEG_EXE):
    AudioSegment.converter = FFMPEG_EXE

# Force HuggingFace hub offline mode by default to avoid unexpected network downloads
os.environ.setdefault("HF_HUB_OFFLINE", "1")

# Default local model directories (no network download needed)
DEFAULT_FW_MODEL = os.path.join(BASE_DIR, "model", "faster-whisper")
DEFAULT_W_MODEL_DIR = os.path.join(BASE_DIR, "model", "whisper")

# recordings and exports are placed at project root (one level above ai_transcriber_gui/)
RECORDINGS_DIR = os.path.join(PROJECT_ROOT, "recordings")
EXPORTS_DIR = os.path.join(PROJECT_ROOT, "exports")
for folder in [RECORDINGS_DIR, EXPORTS_DIR]:
    os.makedirs(folder, exist_ok=True)

# Setup logging to file and console
log_path = os.path.join(EXPORTS_DIR, "transcriber.log")
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


def _import_transcriber():
    """Import Transcriber with absolute-then-relative fallback."""
    try:
        from ai_transcriber_gui.src.stt import Transcriber
        return Transcriber
    except ImportError:
        pass
    try:
        from .src.stt import Transcriber
        return Transcriber
    except ImportError:
        pass
    try:
        from src.stt import Transcriber
        return Transcriber
    except ImportError:
        pass
    return None


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
        # Transcriber (model manager)
        try:
            _Transcriber = _import_transcriber()
            if _Transcriber is None:
                raise ImportError('cannot import Transcriber')
            self.stt = _Transcriber(device=self.device, fw_model_root=DEFAULT_FW_MODEL, w_model_dir=DEFAULT_W_MODEL_DIR)
        except Exception:
            logger.exception('Transcriber 初始化失敗，即時轉錄將無法使用')
            self.stt = None
        self.audio_queue = queue.Queue()
        self.transcribe_thread = None
        self.stop_transcription = False

        # audio device selections (populated later)
        self.record_source_var = tk.StringVar(value="麥克風")
        self.mic_device_var = tk.StringVar(value="")
        self.loopback_device_var = tk.StringVar(value="")
        self.mic_devices = []
        self.loopback_devices = []
        self._device_map = {}
        self._mic_rec_fs = 16000
        self._loop_rec_fs = 16000
        # PyAudio instance if available
        try:
            self.pa = pa.PyAudio() if PA_AVAILABLE else None
        except Exception:
            self.pa = None

        self.setup_ui()

    def setup_ui(self):
        tk.Label(self.root, text="fast-Whisper 地端轉錄工具", font=("Arial", 14, "bold")).pack(pady=8)
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

        # Model selection dropdown (use base/small/medium - executed with faster-whisper)
        model_frame = tk.Frame(self.root)
        model_frame.pack(pady=(6, 0), padx=8, fill=tk.X)
        tk.Label(model_frame, text="模型:").pack(side=tk.LEFT)
        # Present a concise list of six models (faster-whisper and whisper variants)
        available_models = [
            "faster-whisper-base", "faster-whisper-small", "faster-whisper-medium",
            "whisper-base", "whisper-small", "whisper-medium",
        ]
        default_model = "faster-whisper-base"
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

        # Audio source selection UI (Mic / Loopback / Both)
        src_frame = tk.Frame(self.root)
        src_frame.pack(pady=(6, 0), padx=8, fill=tk.X)
        tk.Label(src_frame, text="音源: ").pack(side=tk.LEFT)
        src_options = ["麥克風", "WASAPI Loopback", "雙軌 (Mic + Loopback)"]
        self.src_combo = ttk.Combobox(src_frame, textvariable=self.record_source_var, values=src_options, state="readonly", width=22)
        self.src_combo.pack(side=tk.LEFT, padx=6)

        tk.Label(src_frame, text="麥克風裝置:").pack(side=tk.LEFT, padx=(12, 0))
        self.mic_combo = ttk.Combobox(src_frame, textvariable=self.mic_device_var, values=self.mic_devices, state="readonly", width=80)
        self.mic_combo.pack(side=tk.LEFT, padx=6)

        tk.Label(src_frame, text="Loopback 裝置:").pack(side=tk.LEFT, padx=(12, 0))
        self.loopback_combo = ttk.Combobox(src_frame, textvariable=self.loopback_device_var, values=self.loopback_devices, state="readonly", width=80)
        self.loopback_combo.pack(side=tk.LEFT, padx=6)

        tk.Label(self.root, text="轉錄結果:").pack(anchor="w", padx=18)
        self.result_area = scrolledtext.ScrolledText(self.root, height=24, wrap=tk.WORD)
        self.result_area.pack(padx=18, pady=6, fill=tk.BOTH, expand=True)

        # Progress bar at bottom
        progress_frame = tk.Frame(self.root)
        progress_frame.pack(fill=tk.X, padx=12, pady=(0,12))
        tk.Label(progress_frame, text="狀態:").pack(side=tk.LEFT)
        # volume meter (VU) canvas
        self.vol_canvas = tk.Canvas(progress_frame, width=80, height=16, bg="black", highlightthickness=1, highlightbackground="#444")
        self.vol_canvas.pack(side=tk.LEFT, padx=6)
        # loopback (system) VU meter placed between mic and progress bar
        self.vol_canvas_loop = tk.Canvas(progress_frame, width=80, height=16, bg="#111", highlightthickness=1, highlightbackground="#444")
        self.vol_canvas_loop.pack(side=tk.LEFT, padx=6)
        self.progress = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.progress_label = tk.Label(progress_frame, text="0%")
        self.progress_label.pack(side=tk.LEFT, padx=(6,0))

        # show startup instructions in result area (file + short technical note)
        try:
            # self._show_startup_instructions()
            pass
        except Exception:
            logger.exception('Failed to show startup instructions')

        # scan audio devices to populate comboboxes
        try:
            self.scan_audio_devices()
        except Exception:
            logger.exception('scan_audio_devices failed')

    def log(self, text):
        ts = datetime.now().strftime('%H:%M:%S')
        line = f"[{ts}] {text}\n"
        self.result_area.insert(tk.END, line)
        self.result_area.see(tk.END)
        logger.info(text)

    def scan_audio_devices(self):
        """Populate mic and loopback device lists using soundcard if available."""
        self.mic_devices = []
        self.loopback_devices = []
        self._device_map = {}
        if sc is None:
            return

        # Use include_loopback=True and isloopback attribute to separate real mics from loopback
        try:
            try:
                all_mics = sc.all_microphones(include_loopback=True)
            except TypeError:
                all_mics = sc.all_microphones()
            for dev in all_mics:
                name = getattr(dev, 'name', str(dev))
                is_lb = getattr(dev, 'isloopback', False)
                if is_lb:
                    if name not in self.loopback_devices:
                        self.loopback_devices.append(name)
                        self._device_map[name] = dev  # proper loopback Microphone object
                else:
                    if name not in self.mic_devices:
                        self.mic_devices.append(name)
                        self._device_map[name] = dev
        except Exception:
            pass

        # Supplement with PyAudio devices (covers PyAudioWPatch explicit loopback)
        if self.pa is not None:
            try:
                for i in range(self.pa.get_device_count()):
                    info = self.pa.get_device_info_by_index(i)
                    name = info.get('name', '')
                    max_in = int(info.get('maxInputChannels', 0))
                    if max_in == 0:
                        continue
                    display_name = f"{name} [pa:{i}]"
                    is_loop = ('loop' in name.lower() or 'loopback' in name.lower()
                               or bool(info.get('isLoopback')))
                    if is_loop:
                        if display_name not in self.loopback_devices:
                            self.loopback_devices.append(display_name)
                            self._device_map[display_name] = ('pyaudio', i, info)
                    else:
                        if display_name not in self.mic_devices:
                            self.mic_devices.append(display_name)
                            self._device_map[display_name] = ('pyaudio', i, info)
            except Exception:
                pass

        try:
            self.mic_combo.config(values=self.mic_devices)
            self.loopback_combo.config(values=self.loopback_devices)
            if not self.mic_device_var.get() and self.mic_devices:
                self.mic_device_var.set(self.mic_devices[0])
            if not self.loopback_device_var.get() and self.loopback_devices:
                self.loopback_device_var.set(self.loopback_devices[0])
        except Exception:
            pass

    def start_record_thread(self):
        if self.is_recording:
            return
        if sc is None:
            messagebox.showerror("缺少套件", "soundcard/soundfile 未安裝，無法錄音。請安裝 requirements.txt 中的套件。")
            return

        self.is_recording = True
        try:
            self.btn_record.config(text="⏺ 錄音中...", bg="#cc0000", fg="white")
            self.btn_stop.config(state=tk.NORMAL)
        except Exception:
            pass
        # reset buffer for this recording session
        self.full_audio = []
        self._record_fs = 16000 if self.realtime_var.get() else 48000
        self.stop_transcription = False
        # log chosen audio sources
        src = self.record_source_var.get() if hasattr(self, 'record_source_var') else '麥克風'
        mic_name = self.mic_device_var.get() if hasattr(self, 'mic_device_var') else ''
        lb_name = self.loopback_device_var.get() if hasattr(self, 'loopback_device_var') else ''
        self.log(f"開始錄音 ({src}) - mic: {mic_name or 'default'}, loopback: {lb_name or 'default'})")

        # start transcription thread when realtime enabled
        if self.realtime_var.get():
            self.transcribe_thread = threading.Thread(target=self.transcription_worker, daemon=True)
            self.transcribe_thread.start()

        threading.Thread(target=self._record_logic_with_ui, daemon=True).start()

    def record_logic(self):
        # choose samplerates per-device to avoid real-time resampling by OS
        fs = self._record_fs
        # prepare buffers for possible multi-track recording
        temp_wav_mic = os.path.join(RECORDINGS_DIR, "temp_mic.wav")
        temp_wav_loop = os.path.join(RECORDINGS_DIR, "temp_loopback.wav")

        source = self.record_source_var.get() if hasattr(self, 'record_source_var') else '麥克風'

        try:
            # resolve device objects from names if available
            mic_dev = None
            loop_dev = None
            if sc is not None:
                try:
                    mic_name = self.mic_device_var.get()
                    if mic_name and mic_name in self._device_map:
                        mic_dev = self._device_map[mic_name]
                        # if mapping refers to pyaudio, try to prefer a soundcard object with same name
                        if isinstance(mic_dev, tuple) and mic_dev[0] == 'pyaudio':
                            # obtain current microphone list from soundcard to compare
                            try:
                                current_mics = sc.all_microphones(include_loopback=True)
                            except TypeError:
                                current_mics = sc.all_microphones()
                            sc_obj = None
                            for d in current_mics:
                                if getattr(d, 'name', '') == mic_name:
                                    sc_obj = d
                                    break
                            if sc_obj is not None:
                                mic_dev = sc_obj
                            else:
                                # leave tuple, indicating pyaudio mic
                                pass
                    else:
                        try:
                            mic_dev = sc.default_microphone()
                        except Exception:
                            mic_dev = None
                except Exception:
                    try:
                        mic_dev = sc.default_microphone()
                    except Exception:
                        mic_dev = None

                try:
                    lb_name = self.loopback_device_var.get()
                    # Use _device_map directly — it now stores proper loopback Microphone objects
                    if lb_name and lb_name in self._device_map:
                        loop_dev = self._device_map[lb_name]
                    else:
                        # No selection: find the first loopback device from soundcard
                        try:
                            try:
                                _all = sc.all_microphones(include_loopback=True)
                            except TypeError:
                                _all = sc.all_microphones()
                            loop_dev = next((d for d in _all if getattr(d, 'isloopback', False)), None)
                        except Exception:
                            loop_dev = None
                except Exception:
                    loop_dev = None

            # If pyaudio mapping was used for selected loopback, extract its index
            loop_pa_idx = None
            loop_pa_info = None
            if isinstance(loop_dev, tuple) and loop_dev[0] == 'pyaudio':
                # tuple is ('pyaudio', index, info)
                try:
                    loop_pa_idx = int(loop_dev[1])
                    loop_pa_info = loop_dev[2]
                    # null out loop_dev so we use pyaudio path
                    loop_dev = None
                except Exception:
                    loop_pa_idx = None
                    loop_pa_info = None

            # If pyaudio mapping was used for selected mic, extract its index
            mic_pa_idx = None
            mic_pa_info = None
            if isinstance(mic_dev, tuple) and mic_dev[0] == 'pyaudio':
                try:
                    mic_pa_idx = int(mic_dev[1])
                    mic_pa_info = mic_dev[2]
                    mic_dev = None
                except Exception:
                    mic_pa_idx = None
                    mic_pa_info = None

            # initialize buffers
            self.full_audio = []
            self.full_audio_loop = []

            # determine per-device samplerates (prefer device native rates)
            try:
                mic_fs = None
                if mic_dev is not None and hasattr(mic_dev, 'default_samplerate'):
                    mic_fs = int(getattr(mic_dev, 'default_samplerate') or fs)
            except Exception:
                mic_fs = None
            try:
                loop_fs = None
                if loop_dev is not None and hasattr(loop_dev, 'default_samplerate'):
                    loop_fs = int(getattr(loop_dev, 'default_samplerate') or fs)
            except Exception:
                loop_fs = None

            # fallback to common fs if device-specific not available
            mic_fs = mic_fs or fs
            loop_fs = loop_fs or fs
            # store for use by _save_recording_file
            self._mic_rec_fs = mic_fs
            self._loop_rec_fs = loop_fs

            # Single-source: mic only
            if source == '麥克風' or sc is None:
                # prefer soundcard mic object; if mic_pa_idx is set, use PyAudio path
                if mic_pa_idx is not None and self.pa is not None:
                    try:
                        rate = int(mic_pa_info.get('defaultSampleRate', mic_fs)) if mic_pa_info else mic_fs
                        channels = int(mic_pa_info.get('maxInputChannels', 1)) if mic_pa_info else 1
                        frames = int(rate * 0.2)
                        stream = self.pa.open(format=pa.paInt16, channels=channels, rate=rate,
                                              input=True, frames_per_buffer=frames,
                                              input_device_index=mic_pa_idx)
                        while self.is_recording:
                            raw = stream.read(frames, exception_on_overflow=False)
                            data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                            if channels > 1:
                                data = data.reshape(-1, channels)
                                chunk = np.mean(data, axis=1).astype(np.float32)
                            else:
                                chunk = data
                            try:
                                rms = np.sqrt(np.mean(chunk.astype(np.float64) ** 2))
                                pct = int(min(100, (rms / 0.1) * 100))
                                try:
                                    self.root.after(0, self.update_volume, pct, 0)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                            try:
                                self.full_audio.append(chunk)
                            except Exception:
                                pass
                            if self.realtime_var.get():
                                try:
                                    self.audio_queue.put(chunk, block=False)
                                except Exception:
                                    pass
                        try:
                            stream.stop_stream()
                            stream.close()
                        except Exception:
                            pass
                    except Exception:
                        logger.exception('pyaudio mic read failed')
                        self.log('pyaudio 麥克風讀取失敗，請檢查裝置設定')
                        return
                else:
                    mic = mic_dev if mic_dev is not None else sc.default_microphone() if sc is not None else None
                    if mic is None:
                        self.log('無法取得麥克風裝置。')
                        return
                    # use device-native samplerate for mic recorder
                    with mic.recorder(samplerate=mic_fs, channels=1) as mic_rec:
                        while self.is_recording:
                            # use ~200ms chunks to reduce callback overhead and discontinuities
                            frames = int(mic_fs * 0.2)
                            m_data = mic_rec.record(numframes=frames)
                            chunk = np.mean(m_data, axis=1).astype(np.float32)
                            try:
                                rms = np.sqrt(np.mean(chunk.astype(np.float64) ** 2))
                                pct = int(min(100, (rms / 0.1) * 100))
                                try:
                                    self.root.after(0, self.update_volume, pct, 0)
                                except Exception:
                                    pass
                            except Exception:
                                pass
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
                sf.write(temp_wav_mic, final_array, mic_fs)  # use actual recording rate
                mp3_path = temp_wav_mic
                if AudioSegment is not None:
                    ts = datetime.now().strftime('%m%d_%H%M')
                    mp3_path = os.path.join(RECORDINGS_DIR, f"rec_{ts}.mp3")
                    AudioSegment.from_wav(temp_wav_mic).export(mp3_path, format="mp3")
                    os.remove(temp_wav_mic)

                self.log(f"錄音結束，已存為 {mp3_path}")
                if self.realtime_var.get():
                    self.audio_queue.put(None)
                else:
                    self.run_stt(mp3_path)

            # Loopback only
            elif source == 'WASAPI Loopback':
                # Prefer PyAudio loopback stream if available
                if loop_pa_idx is not None and self.pa is not None:
                    try:
                        rate = int(loop_pa_info.get('defaultSampleRate', loop_fs)) if loop_pa_info else loop_fs
                        channels = int(loop_pa_info.get('maxInputChannels', 2)) if loop_pa_info else 2
                        frames = int(rate * 0.2)
                        stream = self.pa.open(format=pa.paInt16, channels=channels, rate=rate,
                                              input=True, frames_per_buffer=frames,
                                              input_device_index=loop_pa_idx)
                        while self.is_recording:
                            raw = stream.read(frames, exception_on_overflow=False)
                            data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                            if channels > 1:
                                data = data.reshape(-1, channels)
                                lb_chunk = np.mean(data, axis=1).astype(np.float32)
                            else:
                                lb_chunk = data
                            try:
                                rms = np.sqrt(np.mean(lb_chunk.astype(np.float64) ** 2))
                                pct = int(min(100, (rms / 0.1) * 100))
                                try:
                                    self.root.after(0, self.update_volume, 0, pct)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                            try:
                                self.full_audio_loop.append(lb_chunk)
                            except Exception:
                                pass
                            if self.realtime_var.get():
                                try:
                                    self.audio_queue.put(lb_chunk, block=False)
                                except Exception:
                                    pass
                        try:
                            stream.stop_stream()
                            stream.close()
                        except Exception:
                            pass
                    except Exception:
                        logger.exception('pyaudio loopback read failed')
                        self.log('pyaudio loopback 讀取失敗，請檢查裝置設定。')
                        return
                else:
                    loop = loop_dev if loop_dev is not None else (sc.default_speaker() if sc is not None else None)
                    if loop is None:
                        self.log('無法取得 loopback 裝置。')
                        return
                    if not hasattr(loop, 'recorder'):
                        self.log('選取的 loopback 裝置不支援錄製 (recorder)，請改選其他裝置或使用麥克風錄製。')
                        return
                    # prefer 2 channels for loopback, convert to mono later
                    # use device-native samplerate for loopback recorder
                    with loop.recorder(samplerate=loop_fs, channels=2) as lb_rec:
                        while self.is_recording:
                            frames = int(loop_fs * 0.2)
                            lb_data = lb_rec.record(numframes=frames)
                            lb_chunk = np.mean(lb_data, axis=1).astype(np.float32)
                            try:
                                rms = np.sqrt(np.mean(lb_chunk.astype(np.float64) ** 2))
                                pct = int(min(100, (rms / 0.1) * 100))
                                try:
                                    self.root.after(0, self.update_volume, 0, pct)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                            try:
                                self.full_audio_loop.append(lb_chunk)
                            except Exception:
                                pass
                            if self.realtime_var.get():
                                try:
                                    self.audio_queue.put(lb_chunk, block=False)
                                except Exception:
                                    pass

                if not self.full_audio_loop:
                    self.log("Loopback 未捕捉到資料。")
                    return

                final_array = np.concatenate(self.full_audio_loop) if self.full_audio_loop else np.array([], dtype=np.float32)
                sf.write(temp_wav_loop, final_array, loop_fs)  # use actual recording rate
                mp3_path = temp_wav_loop
                if AudioSegment is not None:
                    ts = datetime.now().strftime('%m%d_%H%M')
                    mp3_path = os.path.join(RECORDINGS_DIR, f"loop_{ts}.mp3")
                    AudioSegment.from_wav(temp_wav_loop).export(mp3_path, format="mp3")
                    os.remove(temp_wav_loop)

                self.log(f"Loopback 錄音結束，已存為 {mp3_path}")
                if self.realtime_var.get():
                    self.audio_queue.put(None)
                else:
                    self.run_stt(mp3_path)

            # Dual-track: mic + loopback
            else:
                mic = mic_dev if mic_dev is not None else sc.default_microphone()
                loop = loop_dev if loop_dev is not None else (sc.default_speaker() if sc is not None else None)
                if mic is None:
                    self.log('無法取得麥克風裝置。')
                    return
                if loop is None or not hasattr(loop, 'recorder'):
                    # fallback to mic-only recording if loopback recorder not available
                    self.log('Loopback 裝置不支援 recorder，改以單軌麥克風錄製。')
                    with mic.recorder(samplerate=fs, channels=1) as mic_rec:
                        while self.is_recording:
                            frames = fs * 2 if self.realtime_var.get() else fs // 2
                            m_data = mic_rec.record(numframes=frames)
                            chunk = np.mean(m_data, axis=1).astype(np.float32)
                            try:
                                rms = np.sqrt(np.mean(chunk.astype(np.float64) ** 2))
                                pct = int(min(100, (rms / 0.1) * 100))
                                try:
                                    self.root.after(0, self.update_volume, pct)
                                except Exception:
                                    pass
                            except Exception:
                                pass
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
                    sf.write(temp_wav_mic, final_array, mic_fs)  # use actual recording rate
                    mp3_path = temp_wav_mic
                    if AudioSegment is not None:
                        ts = datetime.now().strftime('%m%d_%H%M')
                        mp3_path = os.path.join(RECORDINGS_DIR, f'rec_{ts}.mp3')
                        AudioSegment.from_wav(temp_wav_mic).export(mp3_path, format='mp3')
                        os.remove(temp_wav_mic)

                    self.log(f"錄音結束，已存為 {mp3_path}")
                    if self.realtime_var.get():
                        self.audio_queue.put(None)
                    else:
                        self.run_stt(mp3_path)
                    return

                # use per-device samplerates and larger chunks for dual-track
                # If either device is a PyAudio mapping, use PyAudio streams accordingly
                if (mic_pa_idx is not None or loop_pa_idx is not None) and self.pa is not None:
                    try:
                        # determine rates and channels
                        m_rate = int(mic_pa_info.get('defaultSampleRate', mic_fs)) if mic_pa_info else mic_fs
                        m_ch = int(mic_pa_info.get('maxInputChannels', 1)) if mic_pa_info else 1
                        l_rate = int(loop_pa_info.get('defaultSampleRate', loop_fs)) if loop_pa_info else loop_fs
                        l_ch = int(loop_pa_info.get('maxInputChannels', 2)) if loop_pa_info else 2

                        frames_m = int(m_rate * 0.2)
                        frames_l = int(l_rate * 0.2)

                        stream_m = None
                        stream_l = None
                        if mic_pa_idx is not None:
                            stream_m = self.pa.open(format=pa.paInt16, channels=m_ch, rate=m_rate,
                                                    input=True, frames_per_buffer=frames_m,
                                                    input_device_index=mic_pa_idx)
                        if loop_pa_idx is not None:
                            stream_l = self.pa.open(format=pa.paInt16, channels=l_ch, rate=l_rate,
                                                    input=True, frames_per_buffer=frames_l,
                                                    input_device_index=loop_pa_idx)

                        # Open soundcard context managers OUTSIDE the loop if stream is None
                        _mic_sc_ctx = mic.recorder(samplerate=mic_fs, channels=1) if stream_m is None and mic is not None else None
                        _loop_sc_ctx = loop.recorder(samplerate=loop_fs, channels=2) if stream_l is None and loop is not None else None
                        _mic_sc_rec = _mic_sc_ctx.__enter__() if _mic_sc_ctx is not None else None
                        _loop_sc_rec = _loop_sc_ctx.__enter__() if _loop_sc_ctx is not None else None
                        try:
                            while self.is_recording:
                                chunk_m = None
                                chunk_l = None
                                if stream_m is not None:
                                    raw_m = stream_m.read(frames_m, exception_on_overflow=False)
                                    data_m = np.frombuffer(raw_m, dtype=np.int16).astype(np.float32) / 32768.0
                                    if m_ch > 1:
                                        data_m = data_m.reshape(-1, m_ch)
                                        chunk_m = np.mean(data_m, axis=1).astype(np.float32)
                                    else:
                                        chunk_m = data_m
                                elif _mic_sc_rec is not None:
                                    m_data = _mic_sc_rec.record(numframes=int(mic_fs * 0.2))
                                    chunk_m = np.mean(m_data, axis=1).astype(np.float32)

                                if stream_l is not None:
                                    raw_l = stream_l.read(frames_l, exception_on_overflow=False)
                                    data_l = np.frombuffer(raw_l, dtype=np.int16).astype(np.float32) / 32768.0
                                    if l_ch > 1:
                                        data_l = data_l.reshape(-1, l_ch)
                                        chunk_l = np.mean(data_l, axis=1).astype(np.float32)
                                    else:
                                        chunk_l = data_l
                                elif _loop_sc_rec is not None:
                                    lb_data = _loop_sc_rec.record(numframes=int(loop_fs * 0.2))
                                    chunk_l = np.mean(lb_data, axis=1).astype(np.float32)

                                # compute levels and store
                                try:
                                    rms = np.sqrt(np.mean(chunk_m.astype(np.float64) ** 2)) if chunk_m is not None else 0
                                    pct = int(min(100, (rms / 0.1) * 100))
                                    rms_l = np.sqrt(np.mean(chunk_l.astype(np.float64) ** 2)) if chunk_l is not None else 0
                                    pct_l = int(min(100, (rms_l / 0.1) * 100))
                                    self.root.after(0, self.update_volume, pct, pct_l)
                                except Exception:
                                    pass
                                try:
                                    if chunk_m is not None:
                                        self.full_audio.append(chunk_m)
                                except Exception:
                                    pass
                                try:
                                    if chunk_l is not None:
                                        self.full_audio_loop.append(chunk_l)
                                except Exception:
                                    pass
                                if self.realtime_var.get() and chunk_m is not None and chunk_l is not None:
                                    try:
                                        self.audio_queue.put((chunk_m, chunk_l), block=False)
                                    except Exception:
                                        pass
                        finally:
                            if _mic_sc_ctx is not None:
                                try:
                                    _mic_sc_ctx.__exit__(None, None, None)
                                except Exception:
                                    pass
                            if _loop_sc_ctx is not None:
                                try:
                                    _loop_sc_ctx.__exit__(None, None, None)
                                except Exception:
                                    pass
                            try:
                                if stream_m is not None:
                                    stream_m.stop_stream(); stream_m.close()
                                if stream_l is not None:
                                    stream_l.stop_stream(); stream_l.close()
                            except Exception:
                                pass
                    except Exception:
                        logger.exception('pyaudio dual-track read failed')
                        self.log('pyaudio 雙軌讀取失敗，改以單軌錄製')
                else:
                    with mic.recorder(samplerate=mic_fs, channels=1) as mic_rec, loop.recorder(samplerate=loop_fs, channels=2) as lb_rec:
                        while self.is_recording:
                            frames_m = int(mic_fs * 0.2)
                            frames_lb = int(loop_fs * 0.2)
                            m_data = mic_rec.record(numframes=frames_m)
                            lb_data = lb_rec.record(numframes=frames_lb)

                            chunk_m = np.mean(m_data, axis=1).astype(np.float32)
                            chunk_lb = np.mean(lb_data, axis=1).astype(np.float32)

                            try:
                                rms = np.sqrt(np.mean(chunk_m.astype(np.float64) ** 2))
                                pct = int(min(100, (rms / 0.1) * 100))
                                try:
                                    rms_lb = np.sqrt(np.mean(chunk_lb.astype(np.float64) ** 2))
                                    pct_lb = int(min(100, (rms_lb / 0.1) * 100))
                                except Exception:
                                    pct_lb = 0
                                self.root.after(0, self.update_volume, pct, pct_lb)
                            except Exception:
                                pass
                            try:
                                self.full_audio.append(chunk_m)
                            except Exception:
                                pass
                            try:
                                self.full_audio_loop.append(chunk_lb)
                            except Exception:
                                pass
                            if self.realtime_var.get():
                                try:
                                    self.audio_queue.put((chunk_m, chunk_lb), block=False)
                                except Exception:
                                    pass

                if not self.full_audio and not self.full_audio_loop:
                    self.log("錄音沒有捕捉到資料。")
                    return

                # write both tracks using device-native rates
                if self.full_audio:
                    final_m = np.concatenate(self.full_audio)
                    sf.write(temp_wav_mic, final_m, mic_fs)
                else:
                    temp_wav_mic = None

                if self.full_audio_loop:
                    final_lb = np.concatenate(self.full_audio_loop)
                    sf.write(temp_wav_loop, final_lb, loop_fs)
                else:
                    temp_wav_loop = None

                ts = datetime.now().strftime('%m%d_%H%M')
                out_paths = []
                if temp_wav_loop:
                    mp3_loop = os.path.join(RECORDINGS_DIR, f'loop_{ts}.mp3') if AudioSegment is not None else temp_wav_loop
                    if AudioSegment is not None:
                        AudioSegment.from_wav(temp_wav_loop).export(mp3_loop, format='mp3')
                        os.remove(temp_wav_loop)
                    out_paths.append(mp3_loop)

                if temp_wav_mic:
                    mp3_mic = os.path.join(RECORDINGS_DIR, f'rec_{ts}.mp3') if AudioSegment is not None else temp_wav_mic
                    if AudioSegment is not None:
                        AudioSegment.from_wav(temp_wav_mic).export(mp3_mic, format='mp3')
                        os.remove(temp_wav_mic)
                    out_paths.append(mp3_mic)

                self.log(f"雙軌錄音結束，已存為: {', '.join(out_paths)}")
                if self.realtime_var.get():
                    self.audio_queue.put(None)
                else:
                    # transcribe each track and merge by simple labeling (loopback first)
                    entries = []
                    for p in out_paths:
                        try:
                            prep = self.prepare_for_stt(p)
                            segs = self.transcribe_file_to_text(prep, self.model_var.get())
                            label = 'System Audio (Loopback)' if 'loop' in os.path.basename(p).lower() else 'Microphone'
                            for s in segs:
                                entries.append({
                                    'start': s.get('start', 0),
                                    'end': s.get('end', 0),
                                    'text': s.get('text', ''),
                                    'source': label
                                })
                            try:
                                if prep != p and os.path.exists(prep):
                                    os.remove(prep)
                            except Exception:
                                pass
                        except Exception:
                            logger.exception('transcription failed for %s', p)

                    # sort by start time and build merged text with labels
                    entries = sorted(entries, key=lambda e: e.get('start', 0))
                    parts = []
                    for e in entries:
                        parts.append(f"--- {e.get('source')} [{e.get('start',0):.2f}-{e.get('end',0):.2f}] ---\n{e.get('text','')}\n")
                    final_text = "\n".join(parts)

                    # save merged result like run_stt does
                    output_txt = os.path.join(EXPORTS_DIR, f"note_{datetime.now().strftime('%m%d_%H%M')}.txt")
                    MEETING_PROMPT = (
                        "你是一個會議助理，請將以下會議逐字稿（STT，自動語音轉文字，可能包含口語、錯字或重複內容）"
                        "重整為一份專業的會議摘要文件。\n\n"
                        "【輸出格式】\n- 會議主題：\n- 議題摘要（條列）：\n- 討論項目摘要：\n- 代辦事項（Action Items）：\n- 結論事項：\n\n"
                    )
                    try:
                        with open(output_txt, 'w', encoding='utf-8') as f:
                            f.write(f"{MEETING_PROMPT}\n{final_text}")
                        self.log(f"文字檔已存至: {output_txt}")
                    except Exception:
                        logger.exception('failed to write merged transcript')

        except Exception as e:
            self.log(f"錄音錯誤: {e}")

    def stop_record(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.log("停止錄音，處理中...")
        try:
            self.root.after(0, self.update_volume, 0, 0)
        except Exception:
            pass

    def _record_logic_with_ui(self):
        """Wrapper around record_logic that restores the record button when done."""
        try:
            self.record_logic()
        finally:
            self.root.after(0, self._restore_record_btn)

    def _restore_record_btn(self):
        try:
            self.btn_record.config(text="錄製麥克風", bg="#f0ad4e", fg="black")
        except Exception:
            pass

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

    def update_volume(self, mic_percent: int, sys_percent: int = None):
        """Update the mic and loopback (system) VU meters.

        `mic_percent` and `sys_percent` are 0-100. If `sys_percent` is None,
        it will be treated as 0.
        """
        try:
            m_pct = max(0, min(100, int(mic_percent)))
        except Exception:
            m_pct = 0
        try:
            s_pct = max(0, min(100, int(sys_percent))) if sys_percent is not None else 0
        except Exception:
            s_pct = 0

        # draw mic canvas
        try:
            w = int(self.vol_canvas.winfo_width() or 80)
            h = int(self.vol_canvas.winfo_height() or 16)
        except Exception:
            w, h = 80, 16
        fill_w = int((m_pct / 100.0) * w)
        if m_pct < 60:
            color_m = '#3bd14b'
        elif m_pct < 85:
            color_m = '#ffd24d'
        else:
            color_m = '#ff4d4f'
        try:
            self.vol_canvas.delete('all')
            self.vol_canvas.create_rectangle(0, 0, w, h, fill='#222', outline='')
            if fill_w > 0:
                self.vol_canvas.create_rectangle(0, 0, fill_w, h, fill=color_m, outline='')
            # label 'm' to indicate microphone
            self.vol_canvas.create_text(4, h//2, anchor='w', fill='#fff', text='m', font=('Arial', 8, 'bold'))
        except Exception:
            pass

        # draw loopback/system canvas
        try:
            w2 = int(self.vol_canvas_loop.winfo_width() or 80)
            h2 = int(self.vol_canvas_loop.winfo_height() or 16)
        except Exception:
            w2, h2 = 80, 16
        fill2 = int((s_pct / 100.0) * w2)
        if s_pct < 60:
            color_s = '#3bd14b'
        elif s_pct < 85:
            color_s = '#ffd24d'
        else:
            color_s = '#ff4d4f'
        try:
            self.vol_canvas_loop.delete('all')
            self.vol_canvas_loop.create_rectangle(0, 0, w2, h2, fill='#222', outline='')
            if fill2 > 0:
                self.vol_canvas_loop.create_rectangle(0, 0, fill2, h2, fill=color_s, outline='')
            # label 's' to indicate system/loopback
            self.vol_canvas_loop.create_text(4, h2//2, anchor='w', fill='#fff', text='s', font=('Arial', 8, 'bold'))
        except Exception:
            pass

    def _show_startup_instructions(self):
        """Load and display STT instruction file and a short accuracy/speed note on startup."""
        try:
            # file is one level above ai_transcriber_gui
            fname = os.path.abspath(os.path.join(BASE_DIR, '.', 'STT(語音轉文字)程式使用說明.txt'))
            header = "--- STT(語音轉文字) 程式使用說明 ---\n\n"
            note = (
                "在相同硬體下，模型越大速度越慢、辨識效果越好；fast-whisper 在相同模型尺寸下會更快\n\n"
                "Accuracy： base < small < medium < large\n"
                "Speed（同模型）： fast-whisper ≫ openai-whisper\n\n"
            )
            if os.path.isfile(fname):
                try:
                    with open(fname, 'r', encoding='utf-8') as fh:
                        content = fh.read()
                except Exception:
                    content = f"無法讀取說明檔: {fname}\n"
                self.result_area.insert(tk.END, header + content + "\n" + note + "---\n\n")
            else:
                self.result_area.insert(tk.END, header + f"說明檔不存在: {fname}\n\n" + note + "---\n\n")
            self.result_area.see(tk.END)
        except Exception:
            logger.exception('Error showing startup instructions')

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
            output_txt = os.path.join(EXPORTS_DIR, f"note_{datetime.now().strftime('%m%d_%H%M')}.txt")
            with open(output_txt, "w", encoding="utf-8") as f:
                f.write(f"{MEETING_PROMPT}\n{raw}")
            self.log(f"部分轉錄已存至: {output_txt}")
            logger.info("Partial result saved to %s", output_txt)
        except Exception as e:
            self.log(f"儲存部分轉錄失敗: {e}")
            logger.exception("_save_partial_result failed")

    def _save_recording_file(self):
        """Write current accumulated realtime recording to an mp3 (mic + loopback mixed)."""
        try:
            mic_audio = getattr(self, 'full_audio', None)
            loop_audio = getattr(self, 'full_audio_loop', None)
            if not mic_audio and not loop_audio:
                return None

            mic_fs = getattr(self, '_mic_rec_fs', 16000)
            loop_fs = getattr(self, '_loop_rec_fs', mic_fs)

            ts = datetime.now().strftime('%m%d_%H%M%S')
            tmp_wav = os.path.join(RECORDINGS_DIR, f'realtime_{ts}.wav')
            mp3_path = os.path.join(RECORDINGS_DIR, f'realtime_{ts}.mp3')

            try:
                arr_mic = np.concatenate(mic_audio) if mic_audio else None
            except Exception:
                arr_mic = None
            try:
                arr_loop = np.concatenate(loop_audio) if loop_audio else None
            except Exception:
                arr_loop = None

            # Mix loopback into mic when samplerates match (typical: both 48k WASAPI)
            write_fs = mic_fs
            if arr_mic is not None and arr_loop is not None and mic_fs == loop_fs:
                n = max(len(arr_mic), len(arr_loop))
                mixed = np.zeros(n, dtype=np.float32)
                mixed[:len(arr_mic)] += arr_mic * 0.6
                mixed[:len(arr_loop)] += arr_loop * 0.6
                np.clip(mixed, -1.0, 1.0, out=mixed)
                arr = mixed
            elif arr_mic is not None:
                arr = arr_mic
            else:
                arr = arr_loop
                write_fs = loop_fs

            sf.write(tmp_wav, arr, write_fs)
            if AudioSegment is not None:
                try:
                    AudioSegment.from_wav(tmp_wav).export(mp3_path, format='mp3')
                    os.remove(tmp_wav)
                except Exception:
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
        # Present a fixed, recommended set of model options.
        # These model names will be run using the faster-whisper runtime.
        return ["base", "small", "medium"]
    def prepare_for_stt(self, input_path: str) -> str:
        """Delegate preparing audio for STT to ai_transcriber_gui.src.stt.prepare_for_stt."""
        try:
            from ai_transcriber_gui.src.stt import prepare_for_stt as _prep
        except Exception:
            try:
                from ai_transcriber_gui.src.utils import prepare_for_stt as _prep
            except Exception:
                _prep = None
        if _prep is None:
            return input_path
        try:
            return _prep(input_path)
        except Exception:
            logger.exception('prepare_for_stt failed')
            return input_path

    def transcribe_file_to_text(self, file_path: str, selected_model: str) -> list:
        """Delegate to `ai_transcriber_gui.stt.Transcriber` if available."""
        try:
            if self.stt is not None:
                return self.stt.transcribe_file_to_text(file_path, selected_model)
        except Exception:
            logger.exception('stt.transcribe_file_to_text failed')
        return []

    def segments_to_text(self, segments: list) -> str:
        """Convert segment list to a plain text block by concatenating texts in order."""
        try:
            if not segments:
                return ''
            segments = sorted(segments, key=lambda s: s.get('start', 0))
            parts = [s.get('text', '') for s in segments]
            return '\n'.join(parts)
        except Exception:
            return ''

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
        selected = self.model_var.get()
        if self.stt is None:
            # Try to lazily initialize
            try:
                _Transcriber = _import_transcriber()
                if _Transcriber is None:
                    raise ImportError('cannot import Transcriber')
                self.stt = _Transcriber(device=self.device, fw_model_root=DEFAULT_FW_MODEL, w_model_dir=DEFAULT_W_MODEL_DIR)
                logger.info('Transcriber lazily initialized in transcription_worker')
            except Exception:
                logger.exception('Transcriber lazy init failed')
                self.log("轉錄引擎未就緒，將僅儲存錄音檔。")
                return
        if self.stt is None:
            self.log("轉錄引擎未就緒，將僅儲存錄音檔。")
            return

        self.start_progress()

        while not self.stop_transcription:
            try:
                item = self.audio_queue.get(timeout=1.0)
            except Exception:
                if not self.is_recording and self.audio_queue.empty():
                    break
                continue

            if item is None:
                break

            try:
                # item may be a numpy array or a tuple (mic, loopback)
                chunk = item
                if isinstance(item, tuple):
                    chunk = item[0] if item[0] is not None else item[1]
                if chunk is None:
                    continue
                txt = self.stt.transcribe_chunk(chunk, selected)
                if txt:
                    self.root.after(0, lambda t=txt: self.result_area.insert(tk.END, t + " "))
                    self.root.after(0, self.result_area.see, tk.END)
            except Exception:
                logger.exception('Realtime transcription error')

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

            # 一般模式 → 使用預處理（離線 downsample 到 16k mono）再轉錄
            source = file_path
            try:
                source = self.prepare_for_stt(file_path)
            except Exception:
                source = file_path

            # perform transcription and collect text
            text = self.transcribe_file_to_text(source, selected)
            self.root.after(0, lambda: self.result_area.insert(tk.END, f"\n--- 完成 ---\n{text}\n"))

            # clean up any temp files created by prepare_for_stt
            try:
                if tmp_src is not None and os.path.isfile(tmp_src):
                    os.remove(tmp_src)
            except Exception:
                pass

            output_txt = os.path.join(EXPORTS_DIR, f"note_{datetime.now().strftime('%m%d_%H%M')}.txt")
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
        selected = self.model_var.get()
        if self.stt is None:
            self.log('轉錄引擎未就緒，無法分段轉錄。')
            return

        # UI callbacks for stt streaming
        def on_segment(txt):
            try:
                self.root.after(0, lambda t=txt: self.result_area.insert(tk.END, t + ' '))
                self.root.after(0, self.result_area.see, tk.END)
            except Exception:
                pass

        def progress_cb(percent):
            try:
                self.progress.config(mode='determinate')
                self.progress['value'] = percent
                self.update_progress_label(percent)
            except Exception:
                pass

        # start progress UI
        try:
            self.progress.config(mode='determinate', maximum=100)
            self.progress['value'] = 0
            self.update_progress_label(0)
            self.start_progress()
        except Exception:
            pass

        try:
            self.stt.transcribe_file_stream(file_path, selected, on_segment=on_segment, progress_callback=progress_cb, chunk_seconds=chunk_seconds)
        except Exception:
            logger.exception('transcribe_file_stream failed')
            self.log('分段轉錄失敗')
        finally:
            self.stop_progress()


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
    import sys as _sys, os as _os
    _here = _os.path.dirname(_os.path.abspath(__file__))
    _parent = _os.path.dirname(_here)
    for _p in [_here, _parent]:
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    main()
