import sys
import time
import math
try:
    import pyaudio
except Exception as e:
    print("pyaudio not available:", e)
    sys.exit(1)
import numpy as np


def rms_from_frames(frames):
    data = b"".join(frames)
    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples * samples)))


def list_input_devices(pa):
    devices = []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if int(info.get('maxInputChannels', 0)) > 0:
            devices.append(info)
    return devices


def test_devices(duration=0.8, rate=16000, chunk=1024):
    pa = pyaudio.PyAudio()
    devices = list_input_devices(pa)
    results = []
    if not devices:
        print('No input devices found')
        pa.terminate()
        return results

    for info in devices:
        idx = int(info['index'])
        channels = int(min(1, info.get('maxInputChannels', 1)))
        print(f"Testing device {idx}: {info.get('name')}")
        try:
            stream = pa.open(format=pyaudio.paInt16,
                             channels=channels,
                             rate=rate,
                             input=True,
                             input_device_index=idx,
                             frames_per_buffer=chunk)
        except Exception as e:
            print(f"  Cannot open device {idx}: {e}")
            results.append((idx, info.get('name'), 0.0, 'open-fail'))
            continue

        frames = []
        num_frames = int(rate / chunk * duration)
        try:
            for _ in range(max(1, num_frames)):
                data = stream.read(chunk, exception_on_overflow=False)
                frames.append(data)
        except Exception as e:
            print(f"  Error reading from device {idx}: {e}")
            results.append((idx, info.get('name'), 0.0, 'read-fail'))
            stream.stop_stream(); stream.close()
            continue

        stream.stop_stream(); stream.close()
        rms = rms_from_frames(frames)
        print(f"  RMS={rms:.1f}")
        results.append((idx, info.get('name'), rms, 'ok'))

    pa.terminate()
    return results


def pick_best(results, threshold=150.0):
    # choose highest RMS above threshold, else fallback to highest RMS
    ok = [r for r in results if r[3] == 'ok']
    if not ok:
        return None
    best = max(ok, key=lambda r: r[2])
    if best[2] >= threshold:
        return best
    return best


def main():
    print('Scanning input devices and testing short capture...')
    results = test_devices()
    if not results:
        print('No test results. Check that the microphone is connected and drivers are installed.')
        return
    best = pick_best(results)
    print('\nSummary:')
    for r in results:
        print(f" - index={r[0]} name={r[1]} rms={r[2]:.1f} status={r[3]}")
    if best:
        print(f"\nRecommended device -> index={best[0]} name={best[1]} (rms={best[2]:.1f})")
        print('Use this index as PyAudio input_device_index when opening streams.')
    else:
        print('No suitable device detected automatically.')


if __name__ == '__main__':
    main()
