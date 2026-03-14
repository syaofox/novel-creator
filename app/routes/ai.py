import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.dependencies import DbSession, NovelServiceDep, NovelService
from app.constants import TEMPLATE_DIR
from app.models import get_china_now

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
    if not chapter or not chapter.content:
        return HTMLResponse(content="当前章节不存在或内容为空，请先保存章节", status_code=400)

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
    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    return templates.TemplateResponse(request, "partials/memory_summary.html", {"book": book})


@router.post("/stream-summary", response_class=HTMLResponse)
async def stream_summary(book_id: int, db: DbSession, service: NovelServiceDep, chapter: int | None = Form(None)):
    book = service.get_book(book_id)
    if not book:
        return HTMLResponse(content="书籍不存在", status_code=404)

    chapter_number = chapter if chapter is not None else (book.current_chapter or 1)
    if chapter_number < 1:
        return HTMLResponse(content="请先至少保存一章内容", status_code=400)

    chapter = service.get_chapter(book_id, chapter_number)
    if not chapter or not chapter.content:
        return HTMLResponse(content=f"第{chapter_number}章内容为空，请先保存章节内容", status_code=400)

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


@router.post("/stream-compress-summary", response_class=HTMLResponse)
async def stream_compress_summary(book_id: int, db: DbSession, service: NovelServiceDep):
    book = service.get_book(book_id)
    if not book:
        return HTMLResponse(content="书籍不存在", status_code=404)

    if not book.memory_summary:
        return HTMLResponse(content="摘要为空，无法压缩", status_code=400)

    async def generate():
        try:
            async for chunk in service.stream_compress_summary(book):
                data = json.dumps({"content": chunk}, ensure_ascii=False)
                yield f"{data}\n"
                await asyncio.sleep(0.01)
            yield json.dumps({"done": True}) + "\n"
        except TimeoutError:
            logger.error("Timeout during streaming compress summary")
            yield json.dumps({"error": "压缩超时，请稍后重试"}) + "\n"
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during streaming compress summary: {e}")
            yield json.dumps({"error": "网络连接失败，请检查网络"}) + "\n"
        except Exception as e:
            logger.exception("Error during streaming compress summary")
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.post("/save-summary", response_class=HTMLResponse)
async def save_summary(book_id: int, db: DbSession, service: NovelServiceDep, summary: str = Form(...)):
    book = service.get_book(book_id)
    if not book:
        return HTMLResponse(content="书籍不存在", status_code=404)
    service.save_summary(book, summary)
    return "<span class='text-success'>保存成功</span>"


@router.post("/compress-summary", response_class=HTMLResponse)
async def compress_summary(request: Request, book_id: int, db: DbSession, service: NovelServiceDep):
    book = service.get_book(book_id)
    if not book:
        return HTMLResponse(content="书籍不存在", status_code=404)

    try:
        compressed = await service.compress_summary(book)
    except TimeoutError:
        logger.error("Timeout during summary compression")
        return HTMLResponse(content="压缩超时，请稍后重试", status_code=504)
    except (OSError, ConnectionError) as e:
        logger.error(f"Network error during summary compression: {e}")
        return HTMLResponse(content="网络连接失败", status_code=503)
    except Exception as e:
        logger.exception("Error during summary compression")
        return HTMLResponse(content=f"压缩摘要失败: {str(e)}", status_code=500)

    service.save_summary(book, compressed)
    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    return templates.TemplateResponse(request, "partials/memory_summary.html", {"book": book})


@router.post("/update-style", response_class=HTMLResponse)
async def update_style(request: Request, book_id: int, db: DbSession, service: NovelServiceDep):
    book = service.get_book(book_id)
    if not book:
        return HTMLResponse(content="书籍不存在", status_code=404)
    form = await request.form()
    style = form.get("style", "")
    service.update_style(book, style)
    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    return templates.TemplateResponse(request, "partials/style_summary.html", {"book": book})
