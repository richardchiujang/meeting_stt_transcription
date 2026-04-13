"""Test loopback recording fix."""
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    import soundcard as sc
except Exception as e:
    print(f'soundcard not available: {e}')
    sys.exit(1)

print('Testing loopback device detection...')
print()

# Test default microphone
mic = sc.default_microphone()
print(f'Default microphone: {mic}')
print()

# Test finding loopback devices
print('Looking for loopback devices using all_microphones(include_loopback=True):')
try:
    all_mics = sc.all_microphones(include_loopback=True)
    loopback_devices = []
    for m in all_mics:
        is_loopback = hasattr(m, 'isloopback') and m.isloopback
        print(f'  - {m.name}: isloopback={is_loopback}, has recorder={hasattr(m, "recorder")}')
        if is_loopback:
            loopback_devices.append(m)
    
    print()
    if loopback_devices:
        print(f'✓ Found {len(loopback_devices)} loopback device(s)')
        selected = loopback_devices[0]
        print(f'  Will use: {selected.name}')
        print(f'  Has recorder: {hasattr(selected, "recorder")}')
    else:
        print('✗ No loopback devices found')
        print('  System audio recording may not work')
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()

print()
print('--- Test complete ---')
