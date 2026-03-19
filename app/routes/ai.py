import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.dependencies import DbSession, NovelServiceDep, NovelService
from app.constants import TEMPLATE_DIR
from app.models import get_china_now
from app.utils.helpers import get_templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books/{book_id}/ai", tags=["ai"])


@router.post("/update-summary", response_class=HTMLResponse)
async def update_summary(request: Request, book_id: int, db: DbSession, service: NovelServiceDep):
    book = service.get_book(book_id)
    if not book:
        return HTMLResponse(content="书籍不存在", status_code=404)

    chapter_number = book.current_chapter or 1
    if chapter_number < 1:
        return HTMLResponse(content="请先完成至少一章内容", status_code=400)

    chapter = service.get_chapter(book_id, chapter_number)
    if not chapter:
        return HTMLResponse(content="当前章节不存在", status_code=400)
    if not chapter.content and not chapter.core_event:
        return HTMLResponse(content="当前章节内容和核心事件都为空，请先填写", status_code=400)

    try:
        new_summary = await service.update_summary(book, chapter_number)
    except TimeoutError:
        logger.error("Timeout during summary update")
        return HTMLResponse(content="更新超时，请稍后重试", status_code=504)
    except (OSError, ConnectionError) as e:
        logger.error(f"Network error during summary update: {e}")
        return HTMLResponse(content="网络连接失败", status_code=503)
    except Exception as e:
        logger.exception("Error during summary update")
        return HTMLResponse(content=f"更新摘要失败: {str(e)}", status_code=500)

    service.save_summary(book, new_summary)
    templates = get_templates()
    return templates.TemplateResponse(request, "partials/memory_summary.html", {"book": book})


@router.post("/stream-summary", response_class=HTMLResponse)
async def stream_summary(book_id: int, db: DbSession, service: NovelServiceDep, chapter: int | None = Form(None)):
    book = service.get_book(book_id)
    if not book:
        return HTMLResponse(content="书籍不存在", status_code=404)

    chapter_number = chapter if chapter is not None else (book.current_chapter or 1)
    if chapter_number < 1:
        return HTMLResponse(content="请先至少保存一章内容", status_code=400)

    chapter_obj = service.get_chapter(book_id, chapter_number)
    if not chapter_obj:
        return HTMLResponse(content=f"第{chapter_number}章不存在", status_code=400)
    if not chapter_obj.content and not chapter_obj.core_event:
        return HTMLResponse(content=f"第{chapter_number}章内容和核心事件都为空，请先填写", status_code=400)

    async def generate():
        try:
            async for chunk in service.stream_update_summary(book, chapter_number):
                data = json.dumps({"content": chunk}, ensure_ascii=False)
                yield f"{data}\n"
                await asyncio.sleep(0.01)
            yield json.dumps({"done": True}) + "\n"
        except TimeoutError:
            logger.error("Timeout during streaming summary update")
            yield json.dumps({"error": "更新超时，请稍后重试"}) + "\n"
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during streaming summary update: {e}")
            yield json.dumps({"error": "网络连接失败，请检查网络"}) + "\n"
        except Exception as e:
            logger.exception("Error during streaming summary update")
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.post("/save-summary", response_class=HTMLResponse)
async def save_summary(
    book_id: int,
    db: DbSession,
    service: NovelServiceDep,
    summary: str = Form(...),
    chapter: int | None = Form(None),
    title: str | None = Form(None),
    core_event: str | None = Form(None),
):
    book = service.get_book(book_id)
    if not book:
        return HTMLResponse(content="书籍不存在", status_code=404)

    service.save_summary(book, summary)

    # 如果提供了标题和核心事件，同时更新章节
    if (title or core_event) and chapter:
        chapter_number = chapter
    elif title or core_event:
        chapter_number = book.current_chapter or 1
    else:
        chapter_number = None

    if chapter_number and (title or core_event):
        chapter_obj = service.get_chapter(book_id, chapter_number)
        if chapter_obj:
            if title:
                service.repo.update_chapter(chapter_obj, title=title)
            if core_event:
                chapter_obj.core_event = core_event
                service.repo.db.commit()

    return "<span class='text-success'>保存成功</span>"


@router.post("/update-style", response_class=HTMLResponse)
async def update_style(request: Request, book_id: int, db: DbSession, service: NovelServiceDep):
    book = service.get_book(book_id)
    if not book:
        return HTMLResponse(content="书籍不存在", status_code=404)
    form = await request.form()
    style = form.get("style", "")
    service.update_style(book, style)
    templates = get_templates()
    return templates.TemplateResponse(request, "partials/style_summary.html", {"book": book})
