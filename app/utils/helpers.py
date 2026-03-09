import re
from pathlib import Path

def get_book_dir(book_id: int) -> Path:
    """返回书籍的根目录路径（books/{book_id}）"""
    return Path("books") / str(book_id)

def extract_title(content: str) -> str:
    """从章节正文中提取标题，假设第一行可能包含标题，或者由AI生成"""
    # 简单实现：查找以“第X章”开头的行，或者取第一行
    lines = content.strip().split('\n')
    for line in lines:
        if re.match(r'^\s*第[0-9一二三四五六七八九十百千万]+章', line):
            return line.strip()
    # 否则取第一行前20字作为标题
    first_line = lines[0].strip() if lines else ""
    return first_line[:20] + "..." if len(first_line) > 20 else first_line