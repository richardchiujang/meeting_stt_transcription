"""Repeatable packaging script for ai_transcriber_gui

Usage:
    python build_exe.py

What it does:
- Copies `ai_transcriber_gui/` into a temp build folder
- Patches the copied `main.py` to set RECORDINGS_DIR/EXPORTS_DIR under %%APPDATA%% and use them
- Runs PyInstaller to produce a Windows .exe (onefile, windowed)
- Bundles `ffmpeg/` and `model/` directories
- Cleans temp build folder on success

Notes:
- Install PyInstaller in the active Python environment: `pip install pyinstaller`
- Adjust the PyInstaller options below if you want a folder build instead of --onefile.
"""
import os
import sys
import shutil
import subprocess
import tempfile
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_APP = ROOT / 'ai_transcriber_gui'
BUILD_DIR = ROOT / 'build_pack'
DIST_DIR = ROOT / 'dist'
SPEC_DIR = ROOT / 'build_spec'

ENTRY_SCRIPT = 'main.py'  # relative inside ai_transcriber_gui

# Conda env to use for the build
CONDA_ENV_PATH = Path(r'D:\conda_envs\lang_learn')
CONDA_EXE = Path(r'D:\anaconda3\Scripts\conda.exe')

# PyInstaller --add-data uses ';' on Windows
ADD_DATA = [
    (SRC_APP / 'ffmpeg', 'ffmpeg'),
    # whisper assets (mel_filters.npz, multilingual.tiktoken, etc.) must be bundled
    # so they are reachable from sys._MEIPASS at runtime.
]


def _whisper_assets_path() -> Path | None:
    """Return the whisper/assets directory from the conda env, or None."""
    candidate = CONDA_ENV_PATH / 'Lib' / 'site-packages' / 'whisper' / 'assets'
    if candidate.is_dir():
        return candidate
    # fallback: ask Python inside the env
    try:
        import subprocess as _sp
        out = _sp.check_output(
            [str(CONDA_ENV_PATH / 'python.exe'), '-c',
             'import whisper, os; print(os.path.join(os.path.dirname(whisper.__file__), "assets"))'],
            text=True
        ).strip()
        p = Path(out)
        if p.is_dir():
            return p
    except Exception:
        pass
    return None

# Marker to avoid double-patching
PATCH_MARKER = '# <AUTO-PATCHED-BY-build_exe.py>'


def prepare_build_copy():
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    shutil.copytree(SRC_APP, BUILD_DIR)
    print(f'Copied source to {BUILD_DIR}')


def patch_main_for_appdata():
    main_path = BUILD_DIR / ENTRY_SCRIPT
    if not main_path.exists():
        raise FileNotFoundError(main_path)

    text = main_path.read_text(encoding='utf-8')
    if PATCH_MARKER in text:
        print('main.py already patched in build copy; skipping patch step')
        return

    patch_snippet = f"""
{PATCH_MARKER}
import sys, os
# When frozen (packaged exe), _DATA_DIR is the folder containing the exe.
# Bundled assets (ffmpeg) live in sys._MEIPASS; user data lives next to the exe.
if getattr(sys, 'frozen', False):
    _DATA_DIR = os.path.dirname(sys.executable)
    BASE_DIR = getattr(sys, '_MEIPASS', _DATA_DIR)  # bundled ffmpeg etc.
else:
    _DATA_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = _DATA_DIR
# User-writable dirs live next to the exe (not inside _MEIPASS temp dir)
RECORDINGS_DIR = os.path.join(_DATA_DIR, 'recordings')
EXPORTS_DIR = os.path.join(_DATA_DIR, 'exports')
MODEL_DIR = os.path.join(_DATA_DIR, 'model')
os.makedirs(RECORDINGS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)
# Ensure downstream code can reference RECORDINGS_DIR/EXPORTS_DIR/MODEL_DIR
"""

    # Insert snippet after the first imports block (after the last import statement before code)
    # We'll put it at top of file
    new_text = patch_snippet + '\n' + text

    # Replace usages of os.path.join("recordings", / "exports", / "model" with their _DATA_DIR counterparts
    new_text = re.sub(r"os\.path\.join\(\s*['\"]recordings['\"]\s*,", "os.path.join(RECORDINGS_DIR,", new_text)
    new_text = re.sub(r"os\.path\.join\(\s*['\"]exports['\"]\s*,", "os.path.join(EXPORTS_DIR,", new_text)
    new_text = re.sub(r"os\.path\.join\(\s*['\"]model['\"]\s*,", "os.path.join(MODEL_DIR,", new_text)

    # Replace folder list creation: for folder in ["recordings", "exports"]
    new_text = new_text.replace("for folder in [\"recordings\", \"exports\"]:", "for folder in [RECORDINGS_DIR, EXPORTS_DIR]:")

    # Replace DEFAULT_FW_MODEL and DEFAULT_W_MODEL_DIR to use MODEL_DIR (next to exe)
    new_text = re.sub(
        r"DEFAULT_FW_MODEL\s*=\s*os\.path\.join\([^,]+,\s*['\"]model['\"]\s*,\s*['\"]faster-whisper['\"]\s*\)",
        "DEFAULT_FW_MODEL = os.path.join(MODEL_DIR, 'faster-whisper')",
        new_text
    )
    new_text = re.sub(
        r"DEFAULT_W_MODEL_DIR\s*=\s*os\.path\.join\([^,]+,\s*['\"]model['\"]\s*,\s*['\"]whisper['\"]\s*\)",
        "DEFAULT_W_MODEL_DIR = os.path.join(MODEL_DIR, 'whisper')",
        new_text
    )

    main_path.write_text(new_text, encoding='utf-8')
    print('Patched main.py in build copy to use exe-relative RECORDINGS_DIR/EXPORTS_DIR/MODEL_DIR')


def build_with_pyinstaller():
    spec_args = [
        '--noconfirm',
        '--onefile',
        '--windowed',
        '--clean',
    ]

    sep = ';' if os.name == 'nt' else ':'

    # Static add-data entries
    data_entries = list(ADD_DATA)

    # Dynamically add whisper/assets if present
    wa = _whisper_assets_path()
    if wa:
        data_entries.append((wa, 'whisper/assets'))
        print(f'Bundling whisper assets from: {wa}')
    else:
        print('Warning: whisper/assets not found; mel_filters.npz errors may occur at runtime')

    for src, dest in data_entries:
        src = Path(src)
        if not src.exists():
            print(f'Warning: add-data source not found: {src} (skipping)')
            continue
        spec_args += ['--add-data', f"{str(src)}{sep}{dest}"]

    entry = BUILD_DIR / ENTRY_SCRIPT
    spec_args.append(str(entry))

    # Use conda run to invoke PyInstaller inside the target env — more reliable
    # than sys.executable when the build script is run from a different Python.
    if CONDA_EXE.exists():
        cmd = [
            str(CONDA_EXE), 'run', '-p', str(CONDA_ENV_PATH),
            'pyinstaller',
        ] + spec_args
    else:
        # fallback: invoke via the env's python directly
        cmd = [str(CONDA_ENV_PATH / 'python.exe'), '-m', 'PyInstaller'] + spec_args

    print('Running PyInstaller:')
    print(' '.join(cmd))

    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode != 0:
        raise RuntimeError('PyInstaller failed')


def main():
    print('Preparing build copy...')
    prepare_build_copy()
    print('Patching main.py...')
    patch_main_for_appdata()
    print('Running PyInstaller... (this may take minutes)')
    build_with_pyinstaller()
    print('Build complete. Output in dist')
    print('Cleaning up temporary build copy...')
    try:
        shutil.rmtree(BUILD_DIR)
    except Exception:
        pass
    print('Done.')


if __name__ == '__main__':
    main()
    