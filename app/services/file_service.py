import os
from pathlib import Path
from typing import Optional

from app.utils.helpers import get_book_dir


def save_chapter(book_id: int, chapter_number: int, content: str):
    """保存章节正文到文件，并提取标题"""
    book_dir = get_book_dir(book_id)
    chapters_dir = book_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    file_path = chapters_dir / f"{chapter_number}.txt"
    file_path.write_text(content, encoding="utf-8")
    # 注意：标题提取在路由层完成，这里不负责


def read_chapter(book_id: int, chapter_number: int) -> str:
    """读取章节正文"""
    book_dir = get_book_dir(book_id)
    file_path = book_dir / "chapters" / f"{chapter_number}.txt"
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8")


def get_prev_ending(book_id: int, chapter_number: int, chars: int = 600) -> str:
    """获取上一章的最后 chars 字符，如果上一章不存在返回空字符串"""
    if chapter_number <= 1:
        return ""
    prev_content = read_chapter(book_id, chapter_number - 1)
    if not prev_content:
        return ""
    return prev_content[-chars:]


def get_all_chapters_text(book_id: int) -> str:
    """获取所有章节的全文，按顺序拼接"""
    book_dir = get_book_dir(book_id)
    chapters_dir = book_dir / "chapters"
    if not chapters_dir.exists():
        return ""
    chapter_files = sorted(chapters_dir.glob("*.txt"), key=lambda p: int(p.stem))
    texts = []
    for f in chapter_files:
        texts.append(f.read_text(encoding="utf-8"))
    return "\n\n".join(texts)
