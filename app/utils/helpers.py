import logging
import re
from collections.abc import Callable
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.constants import TEMPLATE_DIR

logger = logging.getLogger(__name__)


@lru_cache
def get_templates() -> Jinja2Templates:
    """返回缓存的 Jinja2Templates 单例"""
    return Jinja2Templates(directory=TEMPLATE_DIR)


def get_book_dir(book_id: int) -> Path:
    """返回书籍的根目录路径（books/{book_id}）"""
    return Path("books") / str(book_id)


def extract_title(content: str) -> str:
    """从章节正文中提取标题，假设第一行可能包含标题，或者由AI生成"""
    # 简单实现：查找以"第X章"开头的行，或者取第一行
    lines = content.strip().split("\n")
    for line in lines:
        if re.match(r"^\s*第[0-9一二三四五六七八九十百千万]+章", line):
            return line.strip()
    # 否则取第一行前20字作为标题
    first_line = lines[0].strip() if lines else ""
    return first_line[:20] + "..." if len(first_line) > 20 else first_line


def handle_ai_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """处理 AI 相关错误的装饰器"""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except TimeoutError:
            logger.error("Timeout during AI operation")
            return HTMLResponse(content="请求超时，请稍后重试", status_code=504)
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during AI operation: {e}")
            return HTMLResponse(content="网络连接失败", status_code=503)
        except Exception as e:
            logger.exception("Unexpected error during AI operation")
            import traceback

            return HTMLResponse(content=f"操作失败: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

    return wrapper
