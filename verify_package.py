"""
打包後驗證腳本

用途：檢查打包後的 exe 資源是否完整

執行：
    python verify_package.py
"""
import os
import sys
from pathlib import Path

def check_exists(path: Path, description: str) -> bool:
    """檢查路徑是否存在"""
    exists = path.exists()
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {path}")
    return exists

def check_file_size(path: Path, min_mb: float, max_mb: float) -> bool:
    """檢查檔案大小是否在合理範圍"""
    if not path.exists():
        return False
    
    size_mb = path.stat().st_size / (1024 * 1024)
    in_range = min_mb <= size_mb <= max_mb
    status = "✓" if in_range else "⚠"
    print(f"{status} 大小: {size_mb:.1f} MB (預期: {min_mb}-{max_mb} MB)")
    return in_range

def verify_dist_package():
    """驗證 dist/ 目錄的打包結果"""
    print("=" * 60)
    print("打包結果驗證")
    print("=" * 60)
    
    dist_dir = Path("dist")
    
    if not dist_dir.exists():
        print("✗ dist/ 目錄不存在，請先執行打包")
        return False
    
    all_ok = True
    
    # 檢查主程式
    print("\n【主程式】")
    exe_path = dist_dir / "AI_STT_Transcriber.exe"
    all_ok &= check_exists(exe_path, "主程式")
    if exe_path.exists():
        all_ok &= check_file_size(exe_path, 100, 800)  # 100-800 MB
    
    # 檢查模型
    print("\n【模型檔案】")
    model_base = dist_dir / "model" / "faster-whisper" / "faster-whisper-base"
    all_ok &= check_exists(model_base, "基礎模型目錄")
    
    if model_base.exists():
        all_ok &= check_exists(model_base / "config.json", "模型配置")
        all_ok &= check_exists(model_base / "tokenizer.json", "Tokenizer")
        all_ok &= check_exists(model_base / "vocabulary.txt", "詞彙表")
        
        # 檢查模型檔案（faster-whisper 使用 .bin）
        model_files = list(model_base.glob("model.bin")) + list(model_base.glob("*.safetensors"))
        if model_files:
            print(f"✓ 模型權重檔案: {model_files[0].name}")
        else:
            print("✗ 找不到模型權重檔案 (model.bin 或 *.safetensors)")
            all_ok = False
    
    # 檢查資料夾（會在執行時自動建立）
    print("\n【資料夾】")
    recordings = dist_dir / "recordings"
    exports = dist_dir / "exports"
    
    if recordings.exists():
        print(f"✓ recordings/ 已存在")
    else:
        print(f"ⓘ recordings/ 尚未建立（首次執行時自動建立）")
    
    if exports.exists():
        print(f"✓ exports/ 已存在")
    else:
        print(f"ⓘ exports/ 尚未建立（首次執行時自動建立）")
    
    # 總結
    print("\n" + "=" * 60)
    if all_ok:
        print("✓ 所有必要檔案已就緒，可以進行測試")
        print("\n建議測試步驟：")
        print("  1. cd dist")
        print("  2. .\\AI_STT_Transcriber.exe")
        print("  3. 測試錄音、選檔、轉錄功能")
    else:
        print("⚠ 部分檔案缺失或異常，請檢查打包日誌")
    print("=" * 60)
    
    return all_ok

def verify_source_before_build():
    """打包前檢查原始碼是否完整"""
    print("=" * 60)
    print("打包前檢查")
    print("=" * 60)
    
    all_ok = True
    
    # 檢查 ffmpeg
    print("\n【FFmpeg】")
    ffmpeg = Path("ai_transcriber_gui") / "ffmpeg" / "bin" / "ffmpeg.exe"
    all_ok &= check_exists(ffmpeg, "FFmpeg 執行檔")
    
    # 檢查模型
    print("\n【模型】")
    model_base = Path("ai_transcriber_gui") / "model" / "faster-whisper" / "faster-whisper-base"
    all_ok &= check_exists(model_base, "基礎模型目錄")
    
    if model_base.exists():
        all_ok &= check_exists(model_base / "config.json", "模型配置")
    
    # 檢查原始碼
    print("\n【原始碼】")
    main_py = Path("ai_transcriber_gui") / "main.py"
    all_ok &= check_exists(main_py, "主程式")
    
    src_dir = Path("ai_transcriber_gui") / "src"
    all_ok &= check_exists(src_dir, "src/ 模組目錄")
    
    if src_dir.exists():
        all_ok &= check_exists(src_dir / "stt.py", "STT 引擎")
        all_ok &= check_exists(src_dir / "ui.py", "UI 模組")
        all_ok &= check_exists(src_dir / "recorder.py", "錄音模組")
        all_ok &= check_exists(src_dir / "utils.py", "工具模組")
        all_ok &= check_exists(src_dir / "transcript.py", "逐字稿模組")
        all_ok &= check_exists(src_dir / "devices.py", "裝置模組")
    
    # 檢查 build 腳本
    print("\n【打包腳本】")
    build_script = Path("build_exe.py")
    all_ok &= check_exists(build_script, "打包腳本")
    
    # 總結
    print("\n" + "=" * 60)
    if all_ok:
        print("✓ 所有檔案已就緒，可以執行打包")
        print("\n執行打包指令：")
        print("  python build_exe.py")
    else:
        print("⚠ 部分檔案缺失，請先準備完整資源")
    print("=" * 60)
    
    return all_ok

def main():
    """主程式"""
    import argparse
    parser = argparse.ArgumentParser(description="驗證打包前/後的檔案完整性")
    parser.add_argument("--pre", action="store_true", help="打包前檢查")
    parser.add_argument("--post", action="store_true", help="打包後檢查 (預設)")
    args = parser.parse_args()
    
    if args.pre:
        verify_source_before_build()
    else:
        verify_dist_package()

if __name__ == "__main__":
    main()
