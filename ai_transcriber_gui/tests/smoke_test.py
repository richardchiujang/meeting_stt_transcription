import os
import wave
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RECORDINGS = os.path.join(HERE, '..', 'recordings')
os.makedirs(RECORDINGS, exist_ok=True)

test_wav = os.path.join(RECORDINGS, 'smoke_silence.wav')
sr = 16000
dur = 1
frames = sr * dur

# write 1s silent PCM16 WAV
with wave.open(test_wav, 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sr)
    wf.writeframes(b'\x00\x00' * frames)

print('WAV written:', test_wav, os.path.exists(test_wav))

try:
    from ai_transcriber_gui.src.utils import prepare_for_stt as util_prep
except Exception as e:
    util_prep = None
    print('src.utils.prepare_for_stt import failed:', e)

try:
    from ai_transcriber_gui.src.stt import prepare_for_stt, Transcriber
except Exception as e:
    print('src.stt import failed:', e)
    raise

out = None
try:
    out = prepare_for_stt(test_wav)
    print('prepare_for_stt returned:', out, 'exists=', os.path.exists(out))
except Exception as e:
    print('prepare_for_stt error:', e)

try:
    t = Transcriber(device='cpu', fw_model_root=os.path.join(HERE, '..', 'model', 'faster-whisper'), w_model_dir=os.path.join(HERE, '..', 'model', 'whisper'))
    segs = t.transcribe_file_to_text(out or test_wav, 'faster-whisper-base')
    print('transcribe_file_to_text returned type:', type(segs), 'len=', len(segs) if hasattr(segs, '__len__') else 'N/A')
except Exception as e:
    import traceback
    print('Transcriber test raised:', e)
    traceback.print_exc()

print('SMOKE TEST DONE')
