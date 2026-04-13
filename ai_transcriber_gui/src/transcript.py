"""Transcript formatting and export helpers."""
import os
from datetime import datetime


MEETING_PROMPT = (
    "你是一個會議助理，請將以下會議逐字稿（STT，自動語音轉文字，可能包含口語、錯字或重複內容）"
    "重整為一份專業的會議摘要文件。\n\n"
    "輸出請遵循以下格式與原則：\n\n"
    "【輸出格式】\n"
    "- 會議主題：\n"
    "- 議題摘要（條列）：\n"
    "- 討論項目摘要：\n"
    "- 代辦事項（Action Items）：\n"
    "- 結論事項：\n\n"
    "【整理原則】\n"
    "- 不要逐字翻寫逐字稿，請進行語意理解與摘要\n"
    "- 合併重複內容，移除寒暄與非討論性語句\n"
    "- 若未明確提及負責人，可僅列代辦事項內容\n"
    "- 全文使用繁體中文，條列清楚、結構明確\n\n"
    "---\n"
)


def segments_to_text(segments: list) -> str:
    """Convert a segment list into plain transcript text."""
    try:
        if not segments:
            return ""
        segments = sorted(segments, key=lambda s: s.get('start', 0))
        parts = [s.get('text', '') for s in segments]
        return "\n".join(parts)
    except Exception:
        return ""


def build_note_text(source_path: str, transcript_text: str) -> str:
    return f"{MEETING_PROMPT}\nSource: {source_path}\n\n{transcript_text}"


def save_note(output_dir: str, source_path: str, transcript_text: str) -> str:
    """Save a meeting note txt file and return its path."""
    os.makedirs(output_dir, exist_ok=True)
    output_txt = os.path.join(output_dir, f"note_{datetime.now().strftime('%m%d_%H%M')}.txt")
    with open(output_txt, "w", encoding="utf-8") as fh:
        fh.write(build_note_text(source_path, transcript_text))
    return output_txt


def save_partial_note(output_dir: str, raw_text: str) -> str:
    """Save the current transcript text as a partial note and return its path."""
    os.makedirs(output_dir, exist_ok=True)
    output_txt = os.path.join(output_dir, f"note_{datetime.now().strftime('%m%d_%H%M')}.txt")
    with open(output_txt, "w", encoding="utf-8") as fh:
        fh.write(f"{MEETING_PROMPT}\n{raw_text}")
    return output_txt
