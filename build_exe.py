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

# Additional static data to include alongside the exe
ADD_DATA += [
    (SRC_APP / 'STT(語音轉文字)程式使用說明.txt', '.'),
    (SRC_APP / 'exports', 'exports'),
    (SRC_APP / 'recordings', 'recordings'),
]

# Modules to exclude from the bundled exe (avoid pulling large/unneeded model packages)
EXCLUDE_MODULES = [
    'transformers.models.gemma',
    'transformers.models.gemma2',
    'transformers.models.gemma3',
    'matplotlib',  # 不使用繪圖功能
    'IPython',     # 不需要互動式環境
    'jupyter',     # 不需要 notebook
    'pytest',      # 不需要測試框架
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
    """Patch main.py to use exe-relative directories for recordings/exports/model.
    
    When packaged as .exe:
    - Bundled assets (ffmpeg, whisper/assets) → sys._MEIPASS (temp folder)
    - User data (recordings, exports, model) → exe 所在目錄（可寫入）
    """
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
    """Run PyInstaller to build the .exe with all dependencies.
    
    配置說明：
    - --onefile: 單一 exe 檔案（較慢但方便分發）
    - --windowed: 無 console 視窗（GUI 應用）
    - --clean: 清除暫存檔案
    - --add-data: 打包資源檔案（ffmpeg, whisper assets）
    - --exclude-module: 排除不需要的大型模組
    """
    spec_args = [
        '--noconfirm',
        '--onefile',
        '--windowed',
        '--clean',
        '--name=AI_STT_Transcriber',  # 自訂 exe 檔名
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

    # Add exclude-module flags to avoid bundling large transformer model implementations like Gemma
    for m in EXCLUDE_MODULES:
        spec_args += ['--exclude-module', m]

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


def copy_models_to_dist():
    """Copy model/ directory next to the built exe (not inside it)."""
    src_model = SRC_APP / 'model'
    dst_model = DIST_DIR / 'model'
    if not src_model.is_dir():
        print(f'Warning: model source not found at {src_model}, skipping model copy.')
        return
    if dst_model.exists():
        shutil.rmtree(dst_model)
    shutil.copytree(src_model, dst_model)
    print(f'Copied model/ to {dst_model}')


def main():
    print('='*60)
    print('AI STT GUI 打包工具')
    print('='*60)
    print('\n步驟 1/5: 準備建置目錄...')
    prepare_build_copy()
    print('\n步驟 2/5: 修補 main.py（exe-relative paths）...')
    patch_main_for_appdata()
    print('\n步驟 3/5: 執行 PyInstaller（可能需要數分鐘）...')
    build_with_pyinstaller()
    print('\n步驟 4/5: 複製模型檔案到 dist/...')
    copy_models_to_dist()
    print('\n步驟 5/5: 清理暫存檔案...')
    try:
        shutil.rmtree(BUILD_DIR)
    except Exception:
        pass
    print('\n' + '='*60)
    print('✓ 打包完成！')
    print('='*60)
    print(f'\n輸出位置: {DIST_DIR.resolve()}')
    print('\n使用說明：')
    print('  1. 將 model/ 資料夾放置於 .exe 同層目錄')
    print('  2. 首次執行會自動建立 recordings/ 和 exports/')
    print('  3. 確保 ffmpeg 已打包進 exe（whisper assets 同理）')
    print('\n' + '='*60)


if __name__ == '__main__':
    main()
    