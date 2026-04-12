"""STT helpers and model-related utilities."""
import os
from typing import Optional
try:
    from ai_transcriber_gui.src.utils import prepare_for_stt as _prepare_for_stt
except Exception:
    try:
        from .utils import prepare_for_stt as _prepare_for_stt
    except Exception:
        _prepare_for_stt = None


def prepare_for_stt(input_path: str) -> str:
    """Prepare an audio file for STT (16k mono WAV).

    Delegates to utils.prepare_for_stt when available, otherwise returns
    the original path.
    """
    if _prepare_for_stt is None:
        return input_path
    try:
        return _prepare_for_stt(input_path)
    except Exception:
        return input_path


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


DEFAULT_FW_MODEL = None
DEFAULT_W_MODEL_DIR = None


class Transcriber:
    def __init__(self, device: str = 'cpu', fw_model_root: Optional[str] = None, w_model_dir: Optional[str] = None):
        self.device = device
        self.fw_model = None
        self.model = None
        self.loaded_model_name = None
        # allow overriding defaults (set by main via utils.BASE_DIR if needed)
        self.fw_model_root = fw_model_root
        self.w_model_dir = w_model_dir

    def _model_paths(self):
        return self.fw_model_root, self.w_model_dir

    def _load_fw_model(self, selected_model: str):
        if FWWhisperModel is None:
            raise RuntimeError('faster-whisper not installed')
        model_dir = None
        if self.fw_model_root:
            model_dir = os.path.join(self.fw_model_root, selected_model)
        if not model_dir or not os.path.isdir(model_dir):
            raise RuntimeError(f'Model directory not found: {model_dir}')
        compute_type = 'float16' if self.device == 'cuda' else 'int8'
        self.fw_model = FWWhisperModel(model_dir, device=self.device, compute_type=compute_type)
        self.loaded_model_name = selected_model

    def _load_whisper_model(self, selected_model: str):
        if whisper is None:
            raise RuntimeError('openai-whisper not installed')
        size = selected_model.split('-')[-1]
        self.model = whisper.load_model(size, device=self.device, download_root=self.w_model_dir)
        self.loaded_model_name = selected_model

    def transcribe_file_to_text(self, file_path: str, selected_model: str) -> list:
        try:
            if selected_model.startswith('faster-whisper'):
                if FWWhisperModel is None:
                    return []
                if self.fw_model is None or self.loaded_model_name != selected_model:
                    self._load_fw_model(selected_model)
                ip = ''
                try:
                    segments, _ = self.fw_model.transcribe(file_path, initial_prompt=ip)
                except Exception:
                    segments, _ = self.fw_model.transcribe(file_path)
                out = []
                for s in segments:
                    out.append({'start': getattr(s, 'start', 0), 'end': getattr(s, 'end', 0), 'text': s.text if hasattr(s, 'text') else str(s)})
                return out
            else:
                if whisper is None:
                    return []
                if self.model is None or self.loaded_model_name != selected_model:
                    self._load_whisper_model(selected_model)
                ip = ''
                res = self.model.transcribe(file_path, initial_prompt=ip, fp16=(self.device == 'cuda'))
                segs = res.get('segments', [])
                out = []
                for s in segs:
                    out.append({'start': s.get('start', 0), 'end': s.get('end', 0), 'text': s.get('text', '')})
                return out
        except Exception:
            return []

    def transcribe_chunk(self, chunk, selected_model: str) -> str:
        """Transcribe a numpy float32 chunk and return concatenated text."""
        try:
            if selected_model.startswith('faster-whisper'):
                if self.fw_model is None or self.loaded_model_name != selected_model:
                    self._load_fw_model(selected_model)
                segments, _ = self.fw_model.transcribe(chunk)
                texts = [getattr(s, 'text', str(s)).strip() for s in segments]
                return ' '.join([t for t in texts if t])
            else:
                if self.model is None or self.loaded_model_name != selected_model:
                    self._load_whisper_model(selected_model)
                res = self.model.transcribe(chunk, fp16=(self.device == 'cuda'))
                return res.get('text', '').strip()
        except Exception:
            return ''

    def transcribe_file_stream(self, file_path: str, selected_model: str, on_segment=None, progress_callback=None, chunk_seconds: int = 8):
        """Stream file in chunks and call `on_segment(text)` for each segment found.

        `progress_callback(percent)` is optional and will be called with integer percent.
        """
        tmp_wav = None
        try:
            # try to normalize to wav via utils if available
            try:
                from ai_transcriber_gui.src.utils import AudioSegment as _AS
            except Exception:
                try:
                    from .utils import AudioSegment as _AS
                except Exception:
                    _AS = None
            if _AS is not None:
                tmp_wav = os.path.join('recordings', 'stream_tmp.wav')
                _AS.from_file(file_path).export(tmp_wav, format='wav')
                source = tmp_wav
            else:
                source = file_path

            import soundfile as sfh
            with sfh.SoundFile(source) as fh:
                samplerate = fh.samplerate
                total_frames = len(fh)
                block_frames = int(samplerate * chunk_seconds)
                processed = 0
                # ensure model loaded
                if selected_model.startswith('faster-whisper'):
                    if FWWhisperModel is None:
                        raise RuntimeError('faster-whisper not installed')
                    if self.fw_model is None or self.loaded_model_name != selected_model:
                        self._load_fw_model(selected_model)
                else:
                    if whisper is None:
                        raise RuntimeError('openai-whisper not installed')
                    if self.model is None or self.loaded_model_name != selected_model:
                        self._load_whisper_model(selected_model)

                while True:
                    data = fh.read(frames=block_frames, dtype='float32')
                    if data is None or len(data) == 0:
                        break
                    chunk = data
                    if chunk.ndim > 1:
                        chunk = chunk.mean(axis=1).astype('float32')
                    if samplerate != 16000:
                        import numpy as _np
                        num_out = int(round(len(chunk) * 16000 / samplerate))
                        if num_out > 0:
                            chunk = _np.interp(
                                _np.linspace(0, len(chunk), num_out, endpoint=False),
                                _np.arange(len(chunk)),
                                chunk,
                            ).astype('float32')

                    # transcribe this chunk
                    try:
                        txt = self.transcribe_chunk(chunk, selected_model)
                        if txt and on_segment is not None:
                            on_segment(txt)
                    except Exception:
                        pass

                    processed += len(data)
                    percent = int(min(100, (processed / total_frames) * 100)) if total_frames > 0 else 0
                    if progress_callback is not None:
                        progress_callback(percent)

        finally:
            if tmp_wav is not None:
                try:
                    os.remove(tmp_wav)
                except Exception:
                    pass

    def cleanup_models(self):
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
                except Exception:
                    pass
        except Exception:
            pass


__all__ = ['prepare_for_stt', 'Transcriber']


__all__ = ["prepare_for_stt"]
