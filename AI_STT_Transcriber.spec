# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\Python\\meeting_stt_transcription\\build_pack\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('D:\\Python\\meeting_stt_transcription\\ai_transcriber_gui\\ffmpeg', 'ffmpeg'), ('D:\\Python\\meeting_stt_transcription\\ai_transcriber_gui\\STT(語音轉文字)程式使用說明.txt', '.'), ('C:\\Users\\tw-richard.chiu\\AppData\\Roaming\\Python\\Python312\\site-packages\\whisper\\assets', 'whisper/assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['transformers.models.gemma', 'transformers.models.gemma2', 'transformers.models.gemma3', 'matplotlib', 'IPython', 'jupyter', 'pytest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AI_STT_Transcriber',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
