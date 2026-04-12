import os, sys, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ai_transcriber_gui.src.stt import Transcriber, prepare_for_stt

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MP3 = os.path.join(BASE, 'recordings', 'bq96s64K2YM.mp3')
FW_ROOT = os.path.join(BASE, 'ai_transcriber_gui', 'model', 'faster-whisper')

print('BASE:', BASE)
print('MP3 exists:', os.path.exists(MP3))
print('FW_ROOT:', FW_ROOT, '  exists:', os.path.isdir(FW_ROOT))
print('Model dir:', os.path.join(FW_ROOT, 'faster-whisper-base'), '  exists:', os.path.isdir(os.path.join(FW_ROOT, 'faster-whisper-base')))

t = Transcriber(device='cpu', fw_model_root=FW_ROOT, w_model_dir=os.path.join(BASE, 'ai_transcriber_gui', 'model', 'whisper'))

print('\nPreparing audio...')
src = prepare_for_stt(MP3)
print('prep ->', src, '  exists=', os.path.exists(src))
import os.path; st = os.stat(src); print('WAV size:', st.st_size, 'bytes')

print('\nLoading model...')
try:
    t._load_fw_model('faster-whisper-base')
    print('Model loaded OK:', t.fw_model)
except Exception as e:
    print('LOAD ERROR:', e)
    traceback.print_exc()

print('\nTranscribing...')
try:
    segments_gen, info = t.fw_model.transcribe(src, beam_size=5)
    print('Language detected:', info.language, 'prob:', round(info.language_probability, 2))
    segs = list(segments_gen)
    print(f'Total segments: {len(segs)}')
    for s in segs[:8]:
        print(f'  [{s.start:.1f}-{s.end:.1f}] {s.text}')
except Exception as e:
    print('TRANSCRIBE ERROR:', e)
    traceback.print_exc()

print('\nTEST DONE')
