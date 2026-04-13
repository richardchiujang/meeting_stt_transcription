import os
import threading
import queue
import numpy as np
from datetime import datetime
from typing import Optional
import tkinter as tk
from tkinter import filedialog, messagebox
import logging

try:
    import soundcard as sc
    import soundfile as sf
except Exception:
    sc = None

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

# Force HuggingFace hub offline mode by default to avoid unexpected network downloads
os.environ.setdefault("HF_HUB_OFFLINE", "1")

# Default local model directories (no network download needed)
DEFAULT_FW_MODEL = os.path.join(BASE_DIR, "model", "faster-whisper")
DEFAULT_W_MODEL_DIR = os.path.join(BASE_DIR, "model", "whisper")


def scan_available_models():
    """掃描 model/ 資料夾，動態產生可用模型清單
    
    Returns:
        list: 可用的模型名稱清單
    """
    available = []
    
    # 掃描 faster-whisper 模型（資料夾必須包含 config.json）
    fw_dir = DEFAULT_FW_MODEL
    if os.path.isdir(fw_dir):
        for model_name in os.listdir(fw_dir):
            model_path = os.path.join(fw_dir, model_name)
            config_path = os.path.join(model_path, "config.json")
            if os.path.isdir(model_path) and os.path.isfile(config_path):
                available.append(model_name)
                logger.info(f"找到 Faster-Whisper 模型: {model_name}")
    
    # 掃描 openai-whisper 模型（.pt 檔案）
    w_dir = DEFAULT_W_MODEL_DIR
    if os.path.isdir(w_dir):
        for filename in os.listdir(w_dir):
            if filename.endswith('.pt'):
                # base.pt -> whisper-base
                model_name = f"whisper-{filename[:-3]}"
                available.append(model_name)
                logger.info(f"找到 OpenAI Whisper 模型: {model_name}")
    
    # 如果沒有找到任何模型，返回預設清單（避免程式無法啟動）
    if not available:
        logger.warning("未找到任何模型，使用預設清單")
        available = [
            "faster-whisper-base", "faster-whisper-small", "faster-whisper-medium",
            "whisper-base", "whisper-small", "whisper-medium",
        ]
    
    return sorted(available)

# recordings and exports are placed in a user-local folder (LOCALAPPDATA or home)
try:
    from ai_transcriber_gui.src.utils import get_recordings_dir, get_exports_dir, get_long_path
except Exception:
    try:
        from .src.utils import get_recordings_dir, get_exports_dir, get_long_path
    except Exception:
        from src.utils import get_recordings_dir, get_exports_dir, get_long_path

RECORDINGS_DIR = get_recordings_dir()
EXPORTS_DIR = get_exports_dir()

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


def _import_recorder():
    """Import the single-source recorder helper with absolute-then-relative fallback."""
    try:
        from ai_transcriber_gui.src.recorder import record_single_source
        return record_single_source
    except ImportError:
        pass
    try:
        from .src.recorder import record_single_source
        return record_single_source
    except ImportError:
        pass
    try:
        from src.recorder import record_single_source
        return record_single_source
    except ImportError:
        pass
    return None


def _import_ui():
    """Import UI helper functions with absolute-then-relative fallback."""
    try:
        from ai_transcriber_gui.src.ui import build_main_ui, append_system_message, append_stt_text, update_progress_label, update_volume, show_startup_instructions
        return build_main_ui, append_system_message, append_stt_text, update_progress_label, update_volume, show_startup_instructions
    except ImportError:
        pass
    try:
        from .src.ui import build_main_ui, append_system_message, append_stt_text, update_progress_label, update_volume, show_startup_instructions
        return build_main_ui, append_system_message, append_stt_text, update_progress_label, update_volume, show_startup_instructions
    except ImportError:
        pass
    try:
        from src.ui import build_main_ui, append_system_message, append_stt_text, update_progress_label, update_volume, show_startup_instructions
        return build_main_ui, append_system_message, append_stt_text, update_progress_label, update_volume, show_startup_instructions
    except ImportError:
        pass
    return None


def _import_transcript_utils():
    """Import transcript helpers with absolute-then-relative fallback."""
    try:
        from ai_transcriber_gui.src.transcript import segments_to_text, save_note, save_partial_note
        return segments_to_text, save_note, save_partial_note
    except ImportError:
        pass
    try:
        from .src.transcript import segments_to_text, save_note, save_partial_note
        return segments_to_text, save_note, save_partial_note
    except ImportError:
        pass
    try:
        from src.transcript import segments_to_text, save_note, save_partial_note
        return segments_to_text, save_note, save_partial_note
    except ImportError:
        pass
    return None


def _import_devices():
    """Import audio source helpers with absolute-then-relative fallback."""
    try:
        from ai_transcriber_gui.src.devices import normalize_source, get_available_sources
        return normalize_source, get_available_sources
    except ImportError:
        pass
    try:
        from .src.devices import normalize_source, get_available_sources
        return normalize_source, get_available_sources
    except ImportError:
        pass
    try:
        from src.devices import normalize_source, get_available_sources
        return normalize_source, get_available_sources
    except ImportError:
        pass
    return None


def _import_prepare_for_stt():
    """Import prepare_for_stt helper with absolute-then-relative fallback."""
    try:
        from ai_transcriber_gui.src.stt import prepare_for_stt
        return prepare_for_stt
    except Exception:
        pass
    try:
        from .src.stt import prepare_for_stt
        return prepare_for_stt
    except Exception:
        pass
    try:
        from src.stt import prepare_for_stt
        return prepare_for_stt
    except Exception:
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

        # audio source selection (single source only)
        device_utils = _import_devices()
        default_source = "麥克風"
        if device_utils is not None:
            _, get_available_sources = device_utils
            available_sources = get_available_sources()
            if available_sources:
                default_source = available_sources[0]
        self.record_source_var = tk.StringVar(value=default_source)
        self._mic_rec_fs = 16000

        # 掃描可用模型
        self.available_models = scan_available_models()
        logger.info(f"可用模型: {', '.join(self.available_models)}")

        self.setup_ui()

    def setup_ui(self):
        ui = _import_ui()
        if ui is None:
            raise ImportError('cannot import ui helpers')
        build_main_ui = ui[0]
        build_main_ui(self)

        # show startup instructions in result area (file + short technical note)
        try:
            # self._show_startup_instructions()
            pass
        except Exception:
            logger.exception('Failed to show startup instructions')

        # no per-device selection UI in the simplified flow

    def log(self, text):
        ui = _import_ui()
        if ui is not None:
            ui[1](self, f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
        logger.info(text)
        # ensure file handlers flush promptly when running as exe
        try:
            for h in logger.handlers:
                try:
                    if hasattr(h, 'flush'):
                        h.flush()
                except Exception:
                    pass
        except Exception:
            pass

    def append_stt_text(self, text: str):
        ui = _import_ui()
        if ui is not None:
            ui[2](self, text)

    def scan_audio_devices(self):
        """Kept for compatibility; device selection is no longer exposed in the UI."""
        return

    def start_record_thread(self):
        # Allow the record button to act as a stop when already recording
        if self.is_recording:
            try:
                self.stop_record()
            except Exception:
                pass
            return
        if sc is None:
            messagebox.showerror("缺少套件", "soundcard/soundfile 未安裝，無法錄音。請安裝 requirements.txt 中的套件。")
            return

        self.is_recording = True
        try:
            self.btn_record.config(text="⏺ 錄音中...", bg="#cc0000", fg="white")
            # 即時轉錄模式下，停止錄音並轉錄按鈕鎖住（因為不需要手動停止轉錄）
            # 非即時模式下，停止錄音並轉錄按鈕可用
            if self.realtime_var.get():
                self.btn_stop.config(state=tk.DISABLED)
            else:
                self.btn_stop.config(state=tk.NORMAL)
        except Exception:
            pass
        # reset buffer for this recording session
        self.full_audio = []
        self.stop_transcription = False
        src = self.record_source_var.get() if hasattr(self, 'record_source_var') else '麥克風'
        self.log(f"開始錄音 ({src})")

        # start transcription thread when realtime enabled
        if self.realtime_var.get():
            self.transcribe_thread = threading.Thread(target=self.transcription_worker, daemon=True)
            self.transcribe_thread.start()
            self.log("即時轉錄已啟動")

        threading.Thread(target=self._record_logic_with_ui, daemon=True).start()

    def record_logic(self):
        source = self.record_source_var.get() if hasattr(self, 'record_source_var') else '麥克風'
        device_utils = _import_devices()
        if device_utils is not None:
            normalize_source = device_utils[0]
            source = normalize_source(source)
        else:
            source = source if source in ('麥克風', '系統音') else '麥克風'

        try:
            record_single_source = _import_recorder()
            if record_single_source is None:
                raise ImportError('cannot import record_single_source')

            wav_path = record_single_source(
                source,
                RECORDINGS_DIR,
                stop_callback=lambda: (not self.is_recording) or self.stop_transcription,
                realtime=self.realtime_var.get(),
                on_chunk=lambda chunk: self.audio_queue.put(chunk, block=False) if self.realtime_var.get() else None,
                on_volume=lambda mic_pct, sys_pct: self.root.after(0, self.update_volume, mic_pct, sys_pct),
                logger=self.log,
            )

            if not wav_path:
                self.log('錄音沒有捕捉到資料。')
                return

            if self.realtime_var.get():
                self.audio_queue.put(None)
                self.log("錄音結束，等待即時轉錄完成...")
            else:
                self.log("錄音結束，開始批次轉錄...")
                threading.Thread(target=self.transcribe_selected_file, args=(wav_path,), daemon=True).start()

        except Exception as e:
            self.log(f'錄音錯誤: {e}')

    def stop_record(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.log("停止錄音並轉錄...")
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
        """錄音結束後恢復錄音按鈕與停止按鈕狀態"""
        try:
            self.btn_record.config(text="開始錄音", bg="#f0ad4e", fg="black")
            # 恢復停止按鈕狀態：根據即時轉錄勾選決定
            if self.realtime_var.get():
                self.btn_stop.config(state=tk.DISABLED)
            else:
                self.btn_stop.config(state=tk.NORMAL)
        except Exception:
            pass

    def _build_recording_wav(self, stem: str):
        """Export the accumulated recording as a single WAV file for STT."""
        try:
            try:
                from ai_transcriber_gui.src.utils import resample_array, write_wav
            except Exception:
                try:
                    from .src.utils import resample_array, write_wav
                except Exception:
                    resample_array = None
                    write_wav = None

            mic_audio = getattr(self, 'full_audio', None)
            if not mic_audio:
                return None

            mic_fs = int(getattr(self, '_mic_rec_fs', 16000) or 16000)
            try:
                arr = np.concatenate(mic_audio).astype(np.float32)
            except Exception:
                return None

            out_path = os.path.join(RECORDINGS_DIR, f"{stem}.wav")

            if write_wav is not None and write_wav(out_path, arr, mic_fs):
                return out_path
            sf.write(out_path, arr, mic_fs)
            return out_path
        except Exception:
            logger.exception('_build_recording_wav failed')
            return None

    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Media Files", "*.mp3 *.wav *.mp4 *.mkv *.m4a *.mov *.wmv")])
        if file_path:
            self.log(f"選取檔案: {os.path.basename(file_path)}")
            # 根據即時轉錄勾選決定處理方式
            if self.realtime_var.get():
                self.log("即時轉錄模式：分段處理...")
            else:
                self.log("批次轉錄模式：整檔處理...")
            self.stop_transcription = False
            try:
                t = threading.Thread(target=self.transcribe_selected_file, args=(file_path,), daemon=True)
                t.start()
                self.log(f"轉錄執行緒已啟動 (daemon={t.daemon})")
            except Exception as e:
                # Log and show a messagebox so the user knows something went wrong
                logger.exception('Failed to start transcribe thread')
                try:
                    messagebox.showerror('啟動轉錄失敗', f'無法啟動轉錄執行緒: {e}')
                except Exception:
                    pass

    def transcribe_selected_file(self, file_path: str):
        """Prepare an audio file and transcribe it (realtime stream or batch mode)."""
        prepared_path = file_path
        temp_prepared_path = None
        try:
            self.log(f"開始轉錄: {os.path.basename(file_path)}")
            self.log(f"[TRACE] transcribe_selected_file enter: {file_path}")
            t0 = datetime.now()

            _prepare_for_stt = _import_prepare_for_stt()
            if _prepare_for_stt is None:
                self.log('[TRACE] prepare_for_stt import failed; skipping pre-processing')
                prepared_path = file_path
            else:
                try:
                    prepared_path = _prepare_for_stt(file_path)
                except Exception:
                    logger.exception('prepare_for_stt failed')
                    self.log('前處理音檔失敗，改用原始檔案')
                    prepared_path = file_path
            if prepared_path != file_path:
                temp_prepared_path = prepared_path
                self.log(f"已前處理為 16k mono WAV: {os.path.basename(prepared_path)}")

            # 根據即時轉錄勾選決定轉錄方式
            if self.realtime_var.get():
                # 即時模式：分段串流轉錄
                self.log(f"[TRACE] calling transcribe_file_stream start: {datetime.now().isoformat()}")
                try:
                    self.transcribe_file_stream(prepared_path)
                except Exception:
                    logger.exception('transcribe_file_stream raised')
                    self.log('分段轉錄失敗 (內部例外)，請查看日誌')
                self.log(f"[TRACE] calling transcribe_file_stream end: {datetime.now().isoformat()}")
            else:
                # 批次模式：整檔一次轉錄
                self.log(f"[TRACE] calling transcribe_file_batch start: {datetime.now().isoformat()}")
                try:
                    self.transcribe_file_batch(prepared_path, file_path)
                except Exception:
                    logger.exception('transcribe_file_batch raised')
                    self.log('批次轉錄失敗 (內部例外)，請查看日誌')
                self.log(f"[TRACE] calling transcribe_file_batch end: {datetime.now().isoformat()}")
                
        finally:
            if temp_prepared_path and os.path.isfile(temp_prepared_path):
                try:
                    os.remove(temp_prepared_path)
                except Exception:
                    pass
            try:
                self.log(f"[TRACE] transcribe_selected_file exit (duration): {(datetime.now()-t0).total_seconds():.2f}s")
            except Exception:
                pass

    def transcribe_file_batch(self, prepared_path: str, original_path: str):
        """批次模式：整檔一次轉錄，完成後一次性顯示所有文字"""
        try:
            if self.stt is None:
                self.log("轉錄引擎未就緒，無法轉錄。")
                return

            self.start_progress()
            selected = self.model_var.get()
            language = self._get_language_code()
            initial_prompt = self.get_initial_prompt()
            self.log(f"批次轉錄中，使用模型: {selected}，語言: {language or '自動'}")

            # 整檔轉錄
            transcript_utils = _import_transcript_utils()
            segments_to_text = transcript_utils[0] if transcript_utils is not None else None
            save_note = transcript_utils[1] if transcript_utils is not None else None

            segments = self.stt.transcribe_file_to_text(prepared_path, selected, language=language, initial_prompt=initial_prompt)
            text = segments_to_text(segments) if segments_to_text is not None else ''
            
            # 一次性顯示所有文字
            self.root.after(0, lambda t=text: self.append_stt_text(t))

            # 儲存文字檔
            if save_note is not None:
                output_txt = save_note(EXPORTS_DIR, original_path, text)
            else:
                output_txt = os.path.join(EXPORTS_DIR, f"note_{datetime.now().strftime('%m%d_%H%M')}.txt")
                with open(output_txt, "w", encoding="utf-8") as f:
                    f.write(f"Source: {original_path}\n\n{text}")
            self.log(f"文字檔已存至: {output_txt}")
            self.log("✓ 已完成")
            
        except Exception as e:
            self.log(f"批次轉錄錯誤: {e}")
            logger.exception("transcribe_file_batch failed")
        finally:
            self.stop_progress()

    def start_progress(self, determinate: bool = False):
        try:
            if determinate:
                self.progress.stop()
                self.progress.config(mode='determinate', maximum=100)
                self.progress['value'] = 0
            else:
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
        ui = _import_ui()
        if ui is not None:
            ui[3](self, percent)

    def update_volume(self, mic_percent: int, sys_percent: int = None):
        ui = _import_ui()
        if ui is not None:
            ui[4](self, mic_percent, sys_percent)

    def clear_result_area(self):
        """清除轉錄結果視窗的內容"""
        try:
            self.result_area.delete("1.0", tk.END)
            self.log("已清除轉錄結果。")
        except Exception as e:
            logger.exception("Failed to clear result area")
            self.log(f"清除失敗: {e}")

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
        raw = ""
        try:
            raw = self.result_area.get("1.0", tk.END).strip()
        except Exception:
            raw = ""
        transcript_utils = _import_transcript_utils()
        if transcript_utils is not None:
            _, _, save_partial_note = transcript_utils
            try:
                if raw:
                    output_txt = save_partial_note(EXPORTS_DIR, raw)
                    self.log(f"部分轉錄已存至: {output_txt}")
            except Exception as exc:
                self.log(f"儲存部分轉錄失敗: {exc}")
        # save any audio captured so far (realtime or not)
        try:
            self._save_recording_file()
        except Exception:
            logger.exception("Failed to save recording on stop_transcription_now")

    def _save_recording_file(self):
        """Write current accumulated realtime recording to a WAV file."""
        try:
            ts = datetime.now().strftime('%m%d_%H%M%S')
            wav_path = self._build_recording_wav(f'realtime_{ts}')
            if wav_path is None:
                return None
            self.log(f"已儲存即時錄音檔: {wav_path}")
            return wav_path
        except Exception:
            logger.exception('_save_recording_file failed')
            return None

    def _on_realtime_change(self, *args):
        """當即時轉錄勾選框變更時調整按鈕狀態（僅限非錄音時）"""
        try:
            # 錄音中時按鈕狀態由 start_record_thread 控制，不在此更改
            if self.is_recording:
                return
            # 未錄音時：即時模式鎖住停止按鈕，非即時模式啟用停止按鈕
            if self.realtime_var.get():
                self.btn_stop.config(state=tk.DISABLED)
            else:
                self.btn_stop.config(state=tk.NORMAL)
        except Exception:
            pass

    def _get_language_code(self) -> Optional[str]:
        """Return Whisper language code based on UI selection."""
        mode = getattr(self, 'lang_var', None)
        if mode is None:
            return None
        sel = self.lang_var.get()
        if sel == "主要英文":
            return "en"
        if sel == "主要中文":
            return "zh"
        return None  # auto-detect

    def get_initial_prompt(self):
        """Return initial_prompt text according to language selection."""
        mode = getattr(self, 'lang_var', None)
        if mode is None:
            return "繁體中文與英文混合討論。"
        sel = self.lang_var.get()
        if sel == "主要英文":
            return "This is a technical meeting in English. Use proper English spellings."
        if sel == "主要中文":
            return "以繁體中文為主，夾雜英文術語。"
        return "繁體中文與英文混合討論。"

    def _on_model_change(self, *_args):
        """Reset cached model when selection changes."""
        if self.stt is not None:
            try:
                self.stt.cleanup_models()
            except Exception:
                pass

    def cleanup_models(self):
        # delete model references and free GPU memory if possible
        try:
            if self.stt is not None and hasattr(self.stt, 'cleanup_models'):
                try:
                    self.stt.cleanup_models()
                except Exception:
                    logger.exception('stt.cleanup_models error')
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
            if self.transcribe_thread is not None and self.transcribe_thread.is_alive():
                try:
                    self.transcribe_thread.join(timeout=1.0)
                except Exception:
                    pass
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
        language = self._get_language_code()
        initial_prompt = self.get_initial_prompt()
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

        # 累積音訊 buffer：累積到 2-3 秒再轉錄，避免 chunk 太短
        audio_buffer = []
        buffer_seconds = 0.0
        target_seconds = 2.5  # 累積 2.5 秒再轉錄
        recorder_chunk_seconds = 0.2  # recorder 的 chunk 長度

        while not self.stop_transcription:
            try:
                item = self.audio_queue.get(timeout=1.0)
            except Exception:
                if not self.is_recording and self.audio_queue.empty():
                    # 錄音結束，轉錄剩餘 buffer
                    if audio_buffer:
                        try:
                            combined = np.concatenate(audio_buffer).astype(np.float32)
                            txt = self.stt.transcribe_chunk(combined, selected, language=language, initial_prompt=initial_prompt)
                            if txt:
                                self.root.after(0, lambda t=txt: self.append_stt_text(t))
                        except Exception:
                            logger.exception('Final buffer transcription error')
                    break
                continue

            if item is None:
                # 轉錄剩餘 buffer
                if audio_buffer:
                    try:
                        combined = np.concatenate(audio_buffer).astype(np.float32)
                        txt = self.stt.transcribe_chunk(combined, selected, language=language, initial_prompt=initial_prompt)
                        if txt:
                            self.root.after(0, lambda t=txt: self.append_stt_text(t))
                    except Exception:
                        logger.exception('Final buffer transcription error')
                break

            try:
                # item may be a numpy array or a tuple (mic, loopback)
                chunk = item
                if isinstance(item, tuple):
                    chunk = item[0] if item[0] is not None else item[1]
                if chunk is None:
                    continue
                
                # 累積到 buffer
                audio_buffer.append(chunk)
                buffer_seconds += recorder_chunk_seconds
                
                # 當累積到目標長度時，進行轉錄
                if buffer_seconds >= target_seconds:
                    try:
                        combined = np.concatenate(audio_buffer).astype(np.float32)
                        txt = self.stt.transcribe_chunk(combined, selected, language=language, initial_prompt=initial_prompt)
                        if txt:
                            self.root.after(0, lambda t=txt: self.append_stt_text(t))
                    except Exception:
                        logger.exception('Realtime transcription error')
                    # 清空 buffer
                    audio_buffer = []
                    buffer_seconds = 0.0
                    
            except Exception:
                logger.exception('Chunk processing error')

        self.stop_progress()
        self.log("即時轉錄執行緒結束。")
        # Save any accumulated realtime transcript as a partial note
        try:
            raw = self.result_area.get("1.0", tk.END).strip() if hasattr(self, 'result_area') else ''
        except Exception:
            raw = ''
        if raw:
            try:
                transcript_utils = _import_transcript_utils()
                if transcript_utils is not None:
                    _, _, save_partial_note = transcript_utils
                    try:
                        output_txt = save_partial_note(EXPORTS_DIR, raw)
                        self.log(f"部分轉錄已存至: {output_txt}")
                    except Exception as exc:
                        self.log(f"儲存部分轉錄失敗: {exc}")
            except Exception:
                pass
        self.log("✓ 已完成")
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
            transcript_utils = _import_transcript_utils()
            segments_to_text = transcript_utils[0] if transcript_utils is not None else None
            save_note = transcript_utils[1] if transcript_utils is not None else None

            source = file_path
            try:
                from ai_transcriber_gui.src.stt import prepare_for_stt as _prepare_for_stt
                source = _prepare_for_stt(file_path)
            except Exception:
                source = file_path

            # perform transcription and collect text
            language = self._get_language_code()
            initial_prompt = self.get_initial_prompt()
            segments = self.stt.transcribe_file_to_text(source, selected, language=language, initial_prompt=initial_prompt) if self.stt is not None else []
            text = segments_to_text(segments) if segments_to_text is not None else ''
            self.root.after(0, lambda t=text: self.append_stt_text(t))

            # clean up any temp files created by prepare_for_stt
            try:
                if source != file_path and os.path.isfile(source):
                    os.remove(source)
            except Exception:
                pass

            if save_note is not None:
                output_txt = save_note(EXPORTS_DIR, file_path, text)
            else:
                output_txt = os.path.join(EXPORTS_DIR, f"note_{datetime.now().strftime('%m%d_%H%M')}.txt")
                with open(output_txt, "w", encoding="utf-8") as f:
                    f.write(f"Source: {file_path}\n\n{text}")
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

        self.log(f"開始分段串流轉錄，使用模型: {selected}")

        # UI callbacks for stt streaming
        def on_segment(txt):
            try:
                self.root.after(0, lambda t=txt: self.append_stt_text(t))
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
            self.start_progress(determinate=True)
        except Exception:
            pass

        try:
            language = self._get_language_code()
            initial_prompt = self.get_initial_prompt()
            self.stt.transcribe_file_stream(
                file_path,
                selected,
                on_segment=on_segment,
                progress_callback=progress_cb,
                chunk_seconds=chunk_seconds,
                stop_callback=lambda: self.stop_transcription,
                language=language,
                initial_prompt=initial_prompt,
            )
            
            # 從 UI 讀取轉錄文字並存檔
            try:
                text = self.result_area.get("1.0", tk.END).strip()
                if text:
                    transcript_utils = _import_transcript_utils()
                    save_note = transcript_utils[1] if transcript_utils is not None else None
                    
                    if save_note is not None:
                        output_txt = save_note(EXPORTS_DIR, file_path, text)
                    else:
                        output_txt = os.path.join(EXPORTS_DIR, f"note_{datetime.now().strftime('%m%d_%H%M')}.txt")
                        with open(output_txt, "w", encoding="utf-8") as f:
                            f.write(f"Source: {file_path}\n\n{text}")
                    self.log(f"文字檔已存至: {output_txt}")
            except Exception as e:
                logger.exception('Failed to save transcription file')
                self.log(f'儲存文字檔失敗: {e}')
            
            self.log("✓ 已完成")
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
