"""Audio recording helpers for single-source mic/system capture."""
import os
from datetime import datetime
from typing import Callable, Optional

import numpy as np

try:
    import soundcard as sc
except Exception:
    sc = None

try:
    import soundfile as sf
except Exception:
    sf = None


def record_single_source(
    source: str,
    recordings_dir: str,
    stop_callback: Callable[[], bool],
    *,
    realtime: bool = False,
    on_chunk: Optional[Callable[[np.ndarray], None]] = None,
    on_volume: Optional[Callable[[int, int], None]] = None,
    logger: Optional[Callable[[str], None]] = None,
    chunk_seconds: float = 0.2,
) -> Optional[str]:
    """Record from either the default microphone or the default speaker loopback.

    Returns the written WAV path, or None on failure.
    """
    if sc is None or sf is None:
        raise RuntimeError("soundcard/soundfile not available")

    source = source if source in ("麥克風", "系統音") else "麥克風"
    
    # Get the appropriate device
    if source == "麥克風":
        device = sc.default_microphone()
    else:
        # For system audio, find a loopback device
        device = None
        try:
            all_mics = sc.all_microphones(include_loopback=True)
            for mic in all_mics:
                if hasattr(mic, 'isloopback') and mic.isloopback:
                    device = mic
                    break
        except Exception:
            pass
    
    if device is None or not hasattr(device, "recorder"):
        raise RuntimeError(f"無法取得{source}裝置")

    samplerate = int(getattr(device, "default_samplerate", 16000) or 16000)
    channels = 1 if source == "麥克風" else 2
    frames = max(1, int(samplerate * chunk_seconds))
    chunks = []

    if logger is not None:
        logger(f"開始錄音 ({source})，samplerate={samplerate}, channels={channels}")

    with device.recorder(samplerate=samplerate, channels=channels) as recorder:
        while not stop_callback():
            data = recorder.record(numframes=frames)
            if data is None or len(data) == 0:
                continue
            chunk = np.mean(data, axis=1).astype(np.float32)
            chunks.append(chunk)

            if on_chunk is not None:
                try:
                    on_chunk(chunk)
                except Exception:
                    pass

            if on_volume is not None:
                try:
                    rms = np.sqrt(np.mean(chunk.astype(np.float64) ** 2))
                    pct = int(min(100, (rms / 0.1) * 100))
                    if source == "麥克風":
                        on_volume(pct, 0)
                    else:
                        on_volume(0, pct)
                except Exception:
                    pass

    if not chunks:
        return None

    final_array = np.concatenate(chunks).astype(np.float32)
    os.makedirs(recordings_dir, exist_ok=True)
    stem = "mic" if source == "麥克風" else "sys"
    wav_path = os.path.join(recordings_dir, f"{stem}_{datetime.now().strftime('%m%d_%H%M')}.wav")
    sf.write(wav_path, final_array, samplerate)

    if logger is not None:
        logger(f"{source}錄音結束，已存為 {wav_path}")
    return wav_path
