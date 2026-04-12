import os
import json
try:
    import soundcard as sc
except Exception as e:
    print('soundcard not installed:', e)
    with open(os.path.join('..','exports','devices.txt'), 'w', encoding='utf-8') as f:
        f.write('soundcard not installed: ' + str(e) + '\n')
    raise

out = []
# try microphones (allow include_loopback when available)
try:
    try:
        mics = sc.all_microphones(include_loopback=True)
    except TypeError:
        mics = sc.all_microphones()
except Exception as e:
    mics = []
    print('all_microphones failed:', e)

try:
    sps = sc.all_speakers()
except Exception as e:
    sps = []
    print('all_speakers failed:', e)

for d in mics:
    name = getattr(d, 'name', None) or str(d)
    info = {
        'role': 'microphone',
        'name': name,
        'repr': repr(d),
        'attrs': []
    }
    try:
        # record some common attributes if present
        for a in ('name','channels','default_samplerate','id','platform_name'):
            if hasattr(d, a):
                try:
                    info['attrs'].append((a, getattr(d, a)))
                except Exception:
                    info['attrs'].append((a, 'error'))
    except Exception:
        pass
    out.append(info)

for d in sps:
    name = getattr(d, 'name', None) or str(d)
    info = {
        'role': 'speaker',
        'name': name,
        'repr': repr(d),
        'attrs': []
    }
    try:
        for a in ('name','channels','default_samplerate','id','platform_name'):
            if hasattr(d, a):
                try:
                    info['attrs'].append((a, getattr(d, a)))
                except Exception:
                    info['attrs'].append((a, 'error'))
    except Exception:
        pass
    out.append(info)

os.makedirs(os.path.join('..','exports'), exist_ok=True)
out_file = os.path.join('..','exports','devices.txt')
with open(out_file, 'w', encoding='utf-8') as f:
    f.write('Detected audio devices:\n')
    for e in out:
        f.write(json.dumps(e, ensure_ascii=False) + '\n')

print('Wrote', out_file)
print('--- Devices ---')
for e in out:
    print(json.dumps(e, ensure_ascii=False))
