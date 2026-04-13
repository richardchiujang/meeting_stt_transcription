"""Tkinter UI helpers for the AI STT GUI."""
import os
import tkinter as tk
from tkinter import scrolledtext, ttk

try:
    from ai_transcriber_gui.src.devices import get_available_sources
except Exception:
    try:
        from .devices import get_available_sources
    except Exception:
        def get_available_sources():
            return ["麥克風", "系統音"]


def build_main_ui(app) -> None:
    """Build the main window widgets and bind them to `app`."""
    tk.Label(app.root, text="fast-Whisper 地端轉錄工具", font=("Arial", 14, "bold")).pack(pady=8)
    app.status_label = tk.Label(app.root, text=f"硬體加速: {app.device.upper()}", fg="blue")
    app.status_label.pack()

    btn_frame = tk.Frame(app.root)
    btn_frame.pack(pady=8)

    app.btn_record = tk.Button(btn_frame, text="開始錄音", command=app.start_record_thread, bg="#f0ad4e")
    app.btn_record.grid(row=0, column=0, padx=6)
    app.btn_stop = tk.Button(btn_frame, text="停止錄音並轉錄", command=app.stop_record, bg="#d9534f", fg="white")
    app.btn_stop.grid(row=0, column=1, padx=6)
    tk.Button(btn_frame, text="選取檔案 (音/影)", command=app.select_file, bg="#5bc0de").grid(row=0, column=2, padx=6)

    app.realtime_var = tk.BooleanVar(value=False)
    tk.Checkbutton(btn_frame, text="即時 (chunked) 轉錄", variable=app.realtime_var).grid(row=0, column=3, padx=8)
    app.realtime_var.trace_add("write", app._on_realtime_change)
    app.btn_stop_trans = tk.Button(btn_frame, text="停止轉錄", command=app.stop_transcription_now, bg="#ff6f61")
    app.btn_stop_trans.grid(row=0, column=4, padx=6)
    tk.Button(btn_frame, text="清除", command=app.clear_result_area, bg="#6c757d", fg="white").grid(row=0, column=5, padx=6)

    model_frame = tk.Frame(app.root)
    model_frame.pack(pady=(6, 0), padx=8, fill=tk.X)
    tk.Label(model_frame, text="模型:").pack(side=tk.LEFT)
    # 使用動態掃描的模型清單
    available_models = getattr(app, 'available_models', [
        "faster-whisper-base", "faster-whisper-small", "faster-whisper-medium",
        "whisper-base", "whisper-small", "whisper-medium",
    ])
    # 選擇預設模型（優先選第一個可用的）
    default_model = available_models[0] if available_models else "faster-whisper-base"
    app.model_var = tk.StringVar(value=default_model)
    app.model_combo = ttk.Combobox(model_frame, textvariable=app.model_var, values=available_models, state="readonly", width=20)
    app.model_combo.pack(side=tk.LEFT, padx=6)
    app.model_var.trace_add("write", app._on_model_change)

    tk.Label(model_frame, text="語言模式:").pack(side=tk.LEFT, padx=(12, 0))
    app.lang_var = tk.StringVar(value="系統自動判斷")
    lang_options = ["主要中文", "主要英文", "系統自動判斷"]
    app.lang_combo = ttk.Combobox(model_frame, textvariable=app.lang_var, values=lang_options, state="readonly", width=20)
    app.lang_combo.pack(side=tk.LEFT, padx=6)

    tk.Label(model_frame, text="錄音來源:").pack(side=tk.LEFT, padx=(12, 0))
    src_options = get_available_sources()
    app.src_combo = ttk.Combobox(model_frame, textvariable=app.record_source_var, values=src_options, state="readonly", width=12)
    app.src_combo.pack(side=tk.LEFT, padx=6)

    tk.Label(app.root, text="轉錄結果: ").pack(anchor="w", padx=18)
    app.result_area = scrolledtext.ScrolledText(app.root, height=24, wrap=tk.WORD)
    app.result_area.pack(padx=18, pady=6, fill=tk.BOTH, expand=True)

    tk.Label(app.root, text="系統訊息: ").pack(anchor="w", padx=18)
    app.system_area = scrolledtext.ScrolledText(app.root, height=7, wrap=tk.WORD)
    app.system_area.pack(padx=18, pady=(0, 6), fill=tk.X)

    progress_frame = tk.Frame(app.root)
    progress_frame.pack(fill=tk.X, padx=12, pady=(0, 12))
    tk.Label(progress_frame, text="狀態:").pack(side=tk.LEFT)
    app.vol_canvas = tk.Canvas(progress_frame, width=80, height=16, bg="black", highlightthickness=1, highlightbackground="#444")
    app.vol_canvas.pack(side=tk.LEFT, padx=6)
    app.vol_canvas_loop = tk.Canvas(progress_frame, width=80, height=16, bg="#111", highlightthickness=1, highlightbackground="#444")
    app.vol_canvas_loop.pack(side=tk.LEFT, padx=6)
    app.progress = ttk.Progressbar(progress_frame, mode='indeterminate')
    app.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
    app.progress_label = tk.Label(progress_frame, text="0%")
    app.progress_label.pack(side=tk.LEFT, padx=(6, 0))


def append_system_message(app, text: str) -> None:
    if not text:
        return
    try:
        app.system_area.insert(tk.END, text)
        if not text.endswith("\n"):
            app.system_area.insert(tk.END, "\n")
        app.system_area.see(tk.END)
    except Exception:
        pass


def append_stt_text(app, text: str) -> None:
    if not text:
        return
    try:
        app.result_area.insert(tk.END, text)
        if not text.endswith("\n"):
            app.result_area.insert(tk.END, " ")
        app.result_area.see(tk.END)
    except Exception:
        pass


def update_progress_label(app, percent: int) -> None:
    try:
        app.progress_label.config(text=f"{int(percent)}%")
    except Exception:
        pass


def update_volume(app, mic_percent: int, sys_percent: int = None) -> None:
    try:
        m_pct = max(0, min(100, int(mic_percent)))
    except Exception:
        m_pct = 0
    try:
        s_pct = max(0, min(100, int(sys_percent))) if sys_percent is not None else 0
    except Exception:
        s_pct = 0

    try:
        w = int(app.vol_canvas.winfo_width() or 80)
        h = int(app.vol_canvas.winfo_height() or 16)
    except Exception:
        w, h = 80, 16
    fill_w = int((m_pct / 100.0) * w)
    if m_pct < 60:
        color_m = '#3bd14b'
    elif m_pct < 85:
        color_m = '#ffd24d'
    else:
        color_m = '#ff4d4f'
    try:
        app.vol_canvas.delete('all')
        app.vol_canvas.create_rectangle(0, 0, w, h, fill='#222', outline='')
        if fill_w > 0:
            app.vol_canvas.create_rectangle(0, 0, fill_w, h, fill=color_m, outline='')
        app.vol_canvas.create_text(4, h // 2, anchor='w', fill='#fff', text='m', font=('Arial', 8, 'bold'))
    except Exception:
        pass

    try:
        w2 = int(app.vol_canvas_loop.winfo_width() or 80)
        h2 = int(app.vol_canvas_loop.winfo_height() or 16)
    except Exception:
        w2, h2 = 80, 16
    fill2 = int((s_pct / 100.0) * w2)
    if s_pct < 60:
        color_s = '#3bd14b'
    elif s_pct < 85:
        color_s = '#ffd24d'
    else:
        color_s = '#ff4d4f'
    try:
        app.vol_canvas_loop.delete('all')
        app.vol_canvas_loop.create_rectangle(0, 0, w2, h2, fill='#222', outline='')
        if fill2 > 0:
            app.vol_canvas_loop.create_rectangle(0, 0, fill2, h2, fill=color_s, outline='')
        app.vol_canvas_loop.create_text(4, h2 // 2, anchor='w', fill='#fff', text='s', font=('Arial', 8, 'bold'))
    except Exception:
        pass


def show_startup_instructions(app, base_dir: str) -> None:
    """Load and display the local STT instruction file in the system area."""
    try:
        fname = os.path.abspath(os.path.join(base_dir, '.', 'STT(語音轉文字)程式使用說明.txt'))
        header = "--- STT(語音轉文字) 程式使用說明 ---\n\n"
        note = (
            "在相同硬體下，模型越大速度越慢、辨識效果越好；fast-whisper 在相同模型尺寸下會更快\n\n"
            "Accuracy： base < small < medium < large\n"
            "Speed（同模型）： fast-whisper ≫ openai-whisper\n\n"
        )
        if os.path.isfile(fname):
            try:
                with open(fname, 'r', encoding='utf-8') as fh:
                    content = fh.read()
            except Exception:
                content = f"無法讀取說明檔: {fname}\n"
            message = header + content + "\n" + note + "---\n\n"
        else:
            message = header + f"說明檔不存在: {fname}\n\n" + note + "---\n\n"
        append_system_message(app, message)
    except Exception:
        pass
