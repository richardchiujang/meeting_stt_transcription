import os
import subprocess
from datetime import datetime
try:
    from pydub import AudioSegment
except Exception:
    AudioSegment = None
try:
    import soundfile as sf
except Exception:
    sf = None
import numpy as np


BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # src/
_PKG_DIR = os.path.dirname(BASE_DIR)                    # ai_transcriber_gui/
PROJECT_ROOT = os.path.dirname(_PKG_DIR)                 # project root
RECORDINGS_DIR = os.path.join(PROJECT_ROOT, "recordings")
EXPORTS_DIR = os.path.join(PROJECT_ROOT, "exports")
FFMPEG_BIN = os.path.join(BASE_DIR, "ffmpeg", "bin")
FFMPEG_EXE = os.path.join(FFMPEG_BIN, "ffmpeg.exe")
if os.path.isdir(FFMPEG_BIN):
    os.environ["PATH"] = FFMPEG_BIN + os.pathsep + os.environ.get("PATH", "")

if AudioSegment is not None and os.path.isfile(FFMPEG_EXE):
    try:
        AudioSegment.converter = FFMPEG_EXE
    except Exception:
        pass


def prepare_for_stt(input_path: str, out_dir: str = None, target_sr: int = 16000) -> str:
    """Convert input file to mono WAV at `target_sr`. Returns path to prepared wav.

    Uses pydub (ffmpeg) when available, falls back to calling ffmpeg CLI. If
    conversion fails, returns the original `input_path`.
    """
    if out_dir is None:
        out_dir = RECORDINGS_DIR
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f'prep_{datetime.now().strftime("%m%d_%H%M%S")}.wav')
    # try pydub first
    if AudioSegment is not None:
        try:
            a = AudioSegment.from_file(input_path)
            a = a.set_frame_rate(target_sr).set_channels(1)
            a.export(out_path, format='wav')
            return out_path
        except Exception:
            pass

    # fallback to ffmpeg CLI
    ff = FFMPEG_EXE if os.path.isfile(FFMPEG_EXE) else 'ffmpeg'
    try:
        cmd = [ff, '-y', '-i', input_path, '-ar', str(target_sr), '-ac', '1', out_path]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out_path
    except Exception:
        return input_path


def rms_from_frames(frames: list) -> float:
    """Compute RMS from a list of raw PCM byte frames (int16)."""
    data = b''.join(frames)
    if not data:
        return 0.0
    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples * samples)))


def resample_array(arr: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Simple resample using linear interpolation (numpy)."""
    if orig_sr == target_sr:
        return arr
    num_out = int(round(len(arr) * float(target_sr) / orig_sr))
    if num_out <= 0:
        return np.array([], dtype=np.float32)
    return np.interp(
        np.linspace(0, len(arr), num_out, endpoint=False),
        np.arange(len(arr)),
        arr
    ).astype(np.float32)


def write_wav(path: str, arr: np.ndarray, sr: int) -> bool:
    """Write a numpy float32 array to WAV. Returns True on success."""
    try:
        if sf is not None:
            sf.write(path, arr, sr)
            return True
    except Exception:
        pass
    try:
        import wave
        with wave.open(path, 'wb') as wf:
            nch = 1 if arr.ndim == 1 else arr.shape[1]
            wf.setnchannels(nch)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            int_data = (np.clip(arr, -1.0, 1.0) * 32767).astype(np.int16)
            wf.writeframes(int_data.tobytes())
        return True
    except Exception:
        return False


def safe_remove(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


__all__ = [
    'BASE_DIR', 'FFMPEG_EXE', 'prepare_for_stt', 'rms_from_frames',
    'resample_array', 'write_wav', 'safe_remove'
]
