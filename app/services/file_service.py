from pathlib import Path

from app.utils.helpers import get_book_dir


def delete_book_files(book_id: int):
    """删除书籍相关的所有文件"""
    book_dir = get_book_dir(book_id)
    if book_dir.exists():
        import shutil

        shutil.rmtree(book_dir)
