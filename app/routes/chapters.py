import logging
import re

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.database import get_db
from app.models import Book, Chapter, GlobalConfig
from app.services.ai_service import AiService
from app.utils.config_helper import get_global_config_dict
from app.utils.helpers import extract_title
from app.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_MAX_TOKENS,
    DEFAULT_STREAM,
    DEFAULT_JAILBREAK_PREFIX,
    DEFAULT_SYSTEM_TEMPLATE,
    DEFAULT_MODEL,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books/{book_id}/chapters", tags=["chapters"])


def get_prev_ending_from_db(db: Session, book_id: int, chapter_number: int, chars: int = 600) -> str:
    """从数据库获取上一章的最后 chars 字符"""
    if chapter_number <= 1:
        return ""
    prev_chapter: Chapter | None = (
        db.query(Chapter).filter(Chapter.book_id == book_id, Chapter.chapter_number == chapter_number - 1).first()
    )
    if not prev_chapter:
        return ""
    content = str(prev_chapter.content) if prev_chapter.content is not None else ""
    if not content:
        return ""
    return content[-chars:]


def extract_chapter_outline(memory_summary: str, chapter_number: int) -> str:
    match = re.search(r"【主线进度】\s*\n(.*?)(?=\n【|$)", memory_summary, re.DOTALL)
    if not match:
        return ""
    outline_text = match.group(1).strip()
    lines = outline_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith(f"第{chapter_number}章") or re.match(rf"^{chapter_number}[:、.]", line):
            parts = re.split(r"[:、.]", line, 1)
            if len(parts) > 1:
                return parts[1].strip()
            return line
    if lines:
        idx = chapter_number - 1
        if idx < len(lines):
            line = lines[idx].strip()
            parts = re.split(r"[:、.]", line, 1)
            if len(parts) > 1:
                return parts[1].strip()
            return line
    return ""


@router.get("/write", response_class=HTMLResponse)
async def write_chapter_form(
    request: Request, book_id: int, num: int | None = None, edit: bool = False, db: Session = Depends(get_db)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    if num is not None:
        chapter_num = num
        if chapter_num < 1 or chapter_num > book.target_chapters:
            raise HTTPException(status_code=400, detail="章节号超出范围")
    else:
        chapter_num = int(book.current_chapter) + 1

    chapter = db.query(Chapter).filter(Chapter.book_id == book_id, Chapter.chapter_number == chapter_num).first()

    core_event = (
        chapter.core_event
        if chapter and chapter.core_event
        else extract_chapter_outline(str(book.memory_summary), chapter_num)
    )

    prev_ending = get_prev_ending_from_db(db, book_id, chapter_num)

    is_completed = chapter is not None and chapter.status == "已完成"
    is_editing = is_completed or edit
    existing_content = ""
    if is_editing and chapter:
        existing_content = chapter.content or ""

    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="app/templates")

    if is_completed and not edit:
        return templates.TemplateResponse(
            request,
            "chapter_preview.html",
            {
                "book": book,
                "chapter_number": chapter_num,
                "chapter": chapter,
                "prev_ending": prev_ending,
                "core_event": core_event,
                "content": existing_content,
            },
        )

    return templates.TemplateResponse(
        request,
        "write_chapter.html",
        {
            "book": book,
            "chapter_number": chapter_num,
            "prev_ending": prev_ending,
            "core_event": core_event,
            "editing": is_editing,
            "chapter": chapter,
            "existing_content": existing_content,
        },
    )


@router.post("/", response_class=HTMLResponse)
async def generate_chapter(
    request: Request,
    book_id: int,
    chapter_number: int = Form(None),
    core_event: str = Form(...),
    db: Session = Depends(get_db),
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    if chapter_number is None:
        current = int(book.current_chapter) if book.current_chapter is not None else 0
        chapter_number = current + 1

    prev_ending = get_prev_ending_from_db(db, book_id, int(chapter_number))

    stream = book.config.get("stream", True)
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="app/templates")

    if stream:
        try:
            return templates.TemplateResponse(
                request,
                "partials/edit_chapter.html",
                {
                    "book": book,
                    "chapter_number": chapter_number,
                    "content": "",
                    "stream": True,
                    "core_event": core_event,
                },
            )
        except TimeoutError:
            logger.error("Timeout during template rendering")
            return HTMLResponse(content="请求超时，请稍后重试", status_code=504)
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during rendering: {e}")
            return HTMLResponse(content="网络连接失败", status_code=503)
        except Exception as e:
            logger.exception("Unexpected error during template rendering")
            import traceback

            return HTMLResponse(
                content=f"模板渲染失败: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status_code=500
            )
    else:
        # 非流式模式：生成完整内容
        global_config = get_global_config_dict(db)
        ai_service = AiService(
            api_key=app_settings.deepseek_api_key,
            base_url=app_settings.deepseek_base_url,
            model=global_config.get("default_model") or app_settings.default_model,
            global_config=global_config,
        )
        try:
            content = await ai_service.write_chapter(book, int(chapter_number), core_event, prev_ending)
        except TimeoutError:
            logger.error("Timeout during chapter generation")
            return HTMLResponse(content="生成超时，请稍后重试", status_code=504)
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during chapter generation: {e}")
            return HTMLResponse(content="网络连接失败", status_code=503)
        except Exception as e:
            logger.exception("Error during chapter generation")
            return HTMLResponse(content=f"生成失败: {str(e)}", status_code=500)
        try:
            return templates.TemplateResponse(
                request,
                "partials/edit_chapter.html",
                {
                    "book": book,
                    "chapter_number": chapter_number,
                    "content": content,
                    "stream": False,
                    "core_event": core_event,
                },
            )
        except TimeoutError:
            logger.error("Timeout during template rendering")
            return HTMLResponse(content="请求超时，请稍后重试", status_code=504)
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during rendering: {e}")
            return HTMLResponse(content="网络连接失败", status_code=503)
        except Exception as e:
            logger.exception("Unexpected error during template rendering")
            import traceback

            return HTMLResponse(
                content=f"模板渲染失败: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status_code=500
            )


@router.get("/regenerate", response_class=HTMLResponse)
async def regenerate_chapter(request: Request, book_id: int, num: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    if num < 1 or num > book.target_chapters:
        raise HTTPException(status_code=400, detail="章节号超出范围")

    chapter = db.query(Chapter).filter(Chapter.book_id == book_id, Chapter.chapter_number == num).first()

    core_event = (
        chapter.core_event if chapter and chapter.core_event else extract_chapter_outline(str(book.memory_summary), num)
    )

    prev_ending = get_prev_ending_from_db(db, book_id, num)

    stream = book.config.get("stream", True)
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="app/templates")

    if stream:
        try:
            return templates.TemplateResponse(
                request,
                "partials/edit_chapter.html",
                {
                    "book": book,
                    "chapter_number": num,
                    "content": "",
                    "stream": True,
                    "core_event": core_event,
                    "prev_ending": prev_ending,
                    "regenerate": True,
                },
            )
        except TimeoutError:
            logger.error("Timeout during regenerate template rendering")
            return HTMLResponse(content="请求超时，请稍后重试", status_code=504)
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during regenerate rendering: {e}")
            return HTMLResponse(content="网络连接失败", status_code=503)
        except Exception as e:
            logger.exception("Unexpected error during regenerate template rendering")
            import traceback

            return HTMLResponse(
                content=f"模板渲染失败: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status_code=500
            )
    else:
        global_config = get_global_config_dict(db)
        ai_service = AiService(
            api_key=app_settings.deepseek_api_key,
            base_url=app_settings.deepseek_base_url,
            model=global_config.get("default_model") or app_settings.default_model,
            global_config=global_config,
        )
        try:
            content = await ai_service.write_chapter(book, int(num), core_event, prev_ending)
        except TimeoutError:
            logger.error("Timeout during chapter regeneration")
            return HTMLResponse(content="生成超时，请稍后重试", status_code=504)
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during chapter regeneration: {e}")
            return HTMLResponse(content="网络连接失败", status_code=503)
        except Exception as e:
            logger.exception("Error during chapter regeneration")
            return HTMLResponse(content=f"生成失败: {str(e)}", status_code=500)
        try:
            return templates.TemplateResponse(
                request,
                "partials/edit_chapter.html",
                {
                    "book": book,
                    "chapter_number": num,
                    "content": content,
                    "stream": False,
                    "core_event": core_event,
                    "prev_ending": prev_ending,
                    "regenerate": True,
                },
            )
        except TimeoutError:
            logger.error("Timeout during regenerate template rendering")
            return HTMLResponse(content="请求超时，请稍后重试", status_code=504)
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during regenerate rendering: {e}")
            return HTMLResponse(content="网络连接失败", status_code=503)
        except Exception as e:
            logger.exception("Unexpected error during regenerate template rendering")
            import traceback

            return HTMLResponse(
                content=f"模板渲染失败: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status_code=500
            )


@router.get("/{chapter_num}", response_class=HTMLResponse)
async def read_chapter(request: Request, book_id: int, chapter_num: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    chapter = db.query(Chapter).filter(Chapter.book_id == book_id, Chapter.chapter_number == chapter_num).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    content = chapter.content or ""
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse(
        request, "chapter_view.html", {"book": book, "chapter": chapter, "content": content}
    )


@router.get("/list", response_class=HTMLResponse)
async def get_chapter_list(book_id: int, db: Session = Depends(get_db)):
    """获取章节列表"""
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    chapters = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_number).all()
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("partials/chapter_list.html", {"book": book, "chapters": chapters})


@router.post("/save", response_class=HTMLResponse)
async def save_chapter_endpoint(
    request: Request,
    book_id: int,
    chapter_number: int = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    if chapter_number < 1 or chapter_number > book.target_chapters:
        raise HTTPException(status_code=400, detail="章节号超出范围")

    chapter = db.query(Chapter).filter(Chapter.book_id == book_id, Chapter.chapter_number == chapter_number).first()

    current = int(book.current_chapter) if book.current_chapter is not None else 0

    is_new_chapter = chapter is None
    if is_new_chapter and chapter_number != current + 1:
        raise HTTPException(status_code=400, detail="章节编号不连续")

    title = extract_title(content) or f"第{chapter_number}章"

    try:
        if is_new_chapter:
            chapter = Chapter(
                book_id=book_id, chapter_number=chapter_number, title=title, content=content, status="已完成"
            )
            db.add(chapter)
        else:
            chapter.title = title
            chapter.content = content
            chapter.status = "已完成"
        book.current_chapter = chapter_number
        db.commit()
        db.refresh(chapter)
        chapters = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_number).all()
    except TimeoutError:
        logger.error("Timeout during chapter save")
        return HTMLResponse(content="保存超时，请稍后重试", status_code=504)
    except (OSError, ConnectionError) as e:
        logger.error(f"Network error during chapter save: {e}")
        return HTMLResponse(content="网络连接失败", status_code=503)
    except Exception as e:
        logger.exception("Error during chapter save")
        import traceback

        return HTMLResponse(content=f"保存失败: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="app/templates")
    chapters = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_number).all()
    chapter_list_html = templates.get_template("partials/chapter_list.html").render(book=book, chapters=chapters)
    content_html = templates.get_template("partials/chapter_generated.html").render(
        book=book, chapter=chapter, content=content[:500] + "..."
    )
    oob_html = f'<div id="chapter-list" hx-swap-oob="true">{chapter_list_html}</div>'
    return HTMLResponse(content=oob_html + content_html)


@router.post("/stream")
async def stream_chapter(
    request: Request,
    book_id: int,
    chapter_number: int = Form(None),
    core_event: str = Form(...),
    db: Session = Depends(get_db),
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    if chapter_number is None:
        current = int(book.current_chapter) if book.current_chapter is not None else 0
        chapter_number = current + 1

    prev_ending = get_prev_ending_from_db(db, book_id, chapter_number)

    global_config = get_global_config_dict(db)
    ai_service = AiService(
        api_key=app_settings.deepseek_api_key,
        base_url=app_settings.deepseek_base_url,
        model=global_config.get("default_model") or app_settings.default_model,
        global_config=global_config,
    )

    async def generate():
        try:
            async for chunk in ai_service.stream_write_chapter(book, chapter_number, core_event, prev_ending):
                yield chunk
        except TimeoutError:
            logger.error("Timeout during streaming chapter generation")
            yield "\n\n--- 生成超时，请稍后重试 ---\n"
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during streaming: {e}")
            yield "\n\n--- 网络连接失败 ---\n"
        except Exception as e:
            logger.exception("Error during streaming chapter generation")
            import traceback

            error_msg = f"\n\n--- 生成过程中发生错误 ---\n{str(e)}\n{traceback.format_exc()}\n"
            yield error_msg

    return StreamingResponse(generate(), media_type="text/plain")
