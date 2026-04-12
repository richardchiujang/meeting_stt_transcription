#!/usr/bin/env python3
"""Diagnose audio devices: list soundcard microphones and PyAudio devices.

Run with the same Python you use to start the GUI (important).
Example:
  D:\conda_envs\lang_learn\python ai_transcriber_gui\diagnose_devices.py

This script writes ai_transcriber_gui/exports/devices_diag.txt and prints summary.
"""
import sys
import os
import json
from datetime import datetime

OUT_DIR = os.path.join(os.path.dirname(__file__), 'exports')
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, 'devices_diag.txt')

data = {
    'timestamp': datetime.now().isoformat(),
    'python_executable': sys.executable,
    'soundcard': None,
    'pyaudio': None,
}

def try_soundcard():
    try:
        import soundcard as sc
    except Exception as e:
        return {'error': f'soundcard import failed: {e}'}
    out = {'microphones': []}
    try:
        for m in sc.all_microphones(include_loopback=True):
            try:
                out['microphones'].append({'name': m.name, 'repr': repr(m)})
            except Exception:
                out['microphones'].append({'name': str(m), 'repr': repr(m)})
    except Exception as e:
        out['error'] = f'all_microphones failed: {e}'
    try:
        out['speakers'] = []
        for s in sc.all_speakers():
            try:
                out['speakers'].append({'name': s.name, 'repr': repr(s)})
            except Exception:
                out['speakers'].append({'name': str(s), 'repr': repr(s)})
    except Exception:
        pass
    return out

def try_pyaudio():
    try:
        import pyaudio
    except Exception as e:
        return {'error': f'pyaudio import failed: {e}'}
    p = pyaudio.PyAudio()
    out = {'hostApiCount': p.get_host_api_count(), 'devices': []}
    try:
        for i in range(p.get_device_count()):
            try:
                info = p.get_device_info_by_index(i)
                out['devices'].append(info)
            except Exception as e:
                out['devices'].append({'index': i, 'error': str(e)})
    finally:
        try:
            p.terminate()
        except Exception:
            pass
    return out

if __name__ == '__main__':
    data['soundcard'] = try_soundcard()
    data['pyaudio'] = try_pyaudio()
    try:
        with open(OUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print('Wrote:', OUT_PATH)
    except Exception as e:
        print('Failed to write output:', e)
    # Print concise summary for copy-paste
    print('\n--- Summary ---')
    print('Python:', data.get('python_executable'))
    sc_info = data.get('soundcard')
    if sc_info and isinstance(sc_info, dict):
        if 'error' in sc_info:
            print('soundcard:', sc_info['error'])
        else:
            print('soundcard microphones:')
            for m in sc_info.get('microphones', []):
                print(' -', m.get('name') or m.get('repr'))
    pa_info = data.get('pyaudio')
    if pa_info and isinstance(pa_info, dict):
        if 'error' in pa_info:
            print('pyaudio:', pa_info['error'])
        else:
            print('pyaudio devices:')
            for d in pa_info.get('devices', []):
                name = d.get('name') if isinstance(d, dict) else str(d)
                idx = d.get('index') if isinstance(d, dict) else None
                print(f" - index={idx} name={name}")
    print('\nPlease attach the full file:', OUT_PATH)
