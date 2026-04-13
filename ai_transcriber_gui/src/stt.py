"""STT helpers and model-related utilities."""
import os
from typing import Optional
import logging
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

logger = logging.getLogger('transcriber')


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

    def transcribe_file_to_text(self, file_path: str, selected_model: str, language: Optional[str] = None, initial_prompt: Optional[str] = None) -> list:
        try:
            if selected_model.startswith('faster-whisper'):
                if FWWhisperModel is None:
                    return []
                if self.fw_model is None or self.loaded_model_name != selected_model:
                    self._load_fw_model(selected_model)
                # Build kwargs
                kwargs = {}
                if language is not None:
                    kwargs['language'] = language
                if initial_prompt is not None:
                    kwargs['initial_prompt'] = initial_prompt
                try:
                    segments, _ = self.fw_model.transcribe(file_path, **kwargs)
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
                # Build kwargs
                kwargs = {'fp16': (self.device == 'cuda')}
                if language is not None:
                    kwargs['language'] = language
                if initial_prompt is not None:
                    kwargs['initial_prompt'] = initial_prompt
                res = self.model.transcribe(file_path, **kwargs)
                segs = res.get('segments', [])
                out = []
                for s in segs:
                    out.append({'start': s.get('start', 0), 'end': s.get('end', 0), 'text': s.get('text', '')})
                return out
        except Exception:
            logger.exception('transcribe_file_to_text failed')
            return []

    def transcribe_chunk(self, chunk, selected_model: str, language: Optional[str] = None, initial_prompt: Optional[str] = None) -> str:
        """Transcribe a numpy float32 chunk and return concatenated text.
        
        Args:
            chunk: audio data (numpy array)
            selected_model: model name
            language: language code ('zh', 'en', etc.) or None for auto-detect
            initial_prompt: prompt text to guide the model
        """
        try:
            if selected_model.startswith('faster-whisper'):
                if self.fw_model is None or self.loaded_model_name != selected_model:
                    self._load_fw_model(selected_model)
                # Build kwargs for faster-whisper
                kwargs = {}
                if language is not None:
                    kwargs['language'] = language
                if initial_prompt is not None:
                    kwargs['initial_prompt'] = initial_prompt
                segments, _ = self.fw_model.transcribe(chunk, **kwargs)
                texts = [getattr(s, 'text', str(s)).strip() for s in segments]
                result = ' '.join([t for t in texts if t])
            else:
                if self.model is None or self.loaded_model_name != selected_model:
                    self._load_whisper_model(selected_model)
                # Build kwargs for openai-whisper
                kwargs = {'fp16': (self.device == 'cuda')}
                if language is not None:
                    kwargs['language'] = language
                if initial_prompt is not None:
                    kwargs['initial_prompt'] = initial_prompt
                res = self.model.transcribe(chunk, **kwargs)
                result = res.get('text', '').strip()
            
            # 過濾 prompt 內容：如果轉錄結果只包含 prompt，則忽略
            if initial_prompt and result:
                # 移除標點符號和括號後比對
                import re
                clean_result = re.sub(r'[。，、！？\s.,!?()（）]', '', result).lower()
                clean_prompt = re.sub(r'[。，、！？\s.,!?()（）]', '', initial_prompt).lower()
                
                # 1. 檢查是否完全相同
                if clean_result == clean_prompt:
                    return ''
                
                # 2. 檢查 prompt 是否在結果中佔主要部分（>80%）
                if clean_prompt and len(clean_prompt) > 5:
                    if clean_prompt in clean_result:
                        prompt_ratio = len(clean_prompt) / len(clean_result)
                        if prompt_ratio > 0.8:
                            return ''
                
                # 3. 反向檢查：結果是否為 prompt 的子字串（處理 prompt 變體）
                if len(clean_result) > 5 and clean_result in clean_prompt:
                    # 結果是 prompt 的子集，且長度相近（>70%）
                    if len(clean_result) / len(clean_prompt) > 0.7:
                        return ''
                
                # 4. 檢查 prompt 特徵詞（避免 prompt 常見詞彙進入轉錄）
                prompt_markers = ['混合討論', 'mixeddiscussion', 'technicalmeeting', '夾雜英文術語', 'properspelling']
                for marker in prompt_markers:
                    if marker in clean_result and len(clean_result) < 30:
                        # 短結果包含 prompt 特徵詞 → 很可能是 prompt
                        return ''
            
            return result
        except Exception:
            logger.exception('transcribe_chunk failed')
            return ''

    def transcribe_file_stream(self, file_path: str, selected_model: str, on_segment=None, progress_callback=None, chunk_seconds: int = 8, stop_callback=None, language: Optional[str] = None, initial_prompt: Optional[str] = None):
        """Stream file in chunks and call `on_segment(text)` for each segment found.

        `progress_callback(percent)` is optional and will be called with integer percent.
        `language` and `initial_prompt` are passed to the transcription model.
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

            try:
                import soundfile as sfh
            except Exception:
                logger.exception('soundfile import failed in transcribe_file_stream')
                raise
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
                    if stop_callback is not None:
                        try:
                            if stop_callback():
                                break
                        except Exception:
                            pass

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
                        txt = self.transcribe_chunk(chunk, selected_model, language=language, initial_prompt=initial_prompt)
                        if txt and on_segment is not None:
                            on_segment(txt)
                    except Exception:
                        logger.exception('Error transcribing chunk in stream')

                    if stop_callback is not None:
                        try:
                            if stop_callback():
                                break
                        except Exception:
                            pass

                    processed += len(data)
                    percent = int(min(100, (processed / total_frames) * 100)) if total_frames > 0 else 0
                    if progress_callback is not None:
                        progress_callback(percent)

        except Exception:
            logger.exception('transcribe_file_stream failed')
            raise
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
