import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Book, Chapter, GlobalConfig
from app.services.ai_service import AiService
from app.config import settings as app_settings
from app.utils.config_helper import get_global_config_dict
from app.models import get_china_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books/{book_id}/ai", tags=["ai"])


@router.post("/update-summary", response_class=HTMLResponse)
async def update_summary(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    chapters = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_number).all()
    full_text = "\n\n".join(str(ch.content) for ch in chapters if ch.content)
    global_config = get_global_config_dict(db)
    ai_service = AiService(
        api_key=app_settings.deepseek_api_key,
        base_url=app_settings.deepseek_base_url,
        model=app_settings.default_model,
        global_config=global_config,
    )
    try:
        chapter_number = book.current_chapter or 1
        new_summary = await ai_service.update_summary(book, full_text, chapter_number)
    except TimeoutError:
        logger.error("Timeout during summary update")
        return HTMLResponse(content="更新超时，请稍后重试", status_code=504)
    except (OSError, ConnectionError) as e:
        logger.error(f"Network error during summary update: {e}")
        return HTMLResponse(content="网络连接失败", status_code=503)
    except Exception as e:
        logger.exception("Error during summary update")
        return HTMLResponse(content=f"更新摘要失败: {str(e)}", status_code=500)
    book.memory_summary = new_summary
    book.updated_at = get_china_now()
    db.commit()
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse(request, "partials/memory_summary.html", {"book": book})


@router.post("/stream-summary", response_class=HTMLResponse)
async def stream_summary(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    chapters = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_number).all()
    full_text = "\n\n".join(str(ch.content) for ch in chapters if ch.content)
    global_config = get_global_config_dict(db)
    ai_service = AiService(
        api_key=app_settings.deepseek_api_key,
        base_url=app_settings.deepseek_base_url,
        model=app_settings.default_model,
        global_config=global_config,
    )

    async def generate():
        try:
            chapter_number = book.current_chapter or 1
            async for chunk in ai_service.stream_update_summary(book, full_text, chapter_number):
                yield chunk
        except TimeoutError:
            logger.error("Timeout during streaming summary update")
            yield "\n\n--- 更新超时，请稍后重试 ---\n"
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during streaming summary update: {e}")
            yield "\n\n--- 网络连接失败 ---\n"
        except Exception as e:
            logger.exception("Error during streaming summary update")
            import traceback

            error_msg = f"\n\n--- 更新过程中发生错误 ---\n{str(e)}\n{traceback.format_exc()}\n"
            yield error_msg

    return StreamingResponse(generate(), media_type="text/plain")


class SummarySaveRequest(BaseModel):
    summary: str


@router.post("/save-summary")
async def save_summary(book_id: int, request: SummarySaveRequest, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    book.memory_summary = request.summary
    book.updated_at = get_china_now()
    db.commit()
    return {"status": "ok"}


@router.get("/global-review", response_class=HTMLResponse)
async def global_review(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    global_config = get_global_config_dict(db)
    ai_service = AiService(
        api_key=app_settings.deepseek_api_key,
        base_url=app_settings.deepseek_base_url,
        model=app_settings.default_model,
        global_config=global_config,
    )
    try:
        review_result = await ai_service.global_review(book)
    except TimeoutError:
        logger.error("Timeout during global review")
        return HTMLResponse(content="回顾超时，请稍后重试", status_code=504)
    except (OSError, ConnectionError) as e:
        logger.error(f"Network error during global review: {e}")
        return HTMLResponse(content="网络连接失败", status_code=503)
    except Exception as e:
        logger.exception("Error during global review")
        return HTMLResponse(content=f"回顾失败: {str(e)}", status_code=500)
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse(request, "partials/review_result.html", {"review": review_result})


@router.post("/compress-summary", response_class=HTMLResponse)
async def compress_summary(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    global_config = get_global_config_dict(db)
    ai_service = AiService(
        api_key=app_settings.deepseek_api_key,
        base_url=app_settings.deepseek_base_url,
        model=app_settings.default_model,
        global_config=global_config,
    )
    try:
        compressed = await ai_service.compress_summary(book)
    except TimeoutError:
        logger.error("Timeout during summary compression")
        return HTMLResponse(content="压缩超时，请稍后重试", status_code=504)
    except (OSError, ConnectionError) as e:
        logger.error(f"Network error during summary compression: {e}")
        return HTMLResponse(content="网络连接失败", status_code=503)
    except Exception as e:
        logger.exception("Error during summary compression")
        return HTMLResponse(content=f"压缩摘要失败: {str(e)}", status_code=500)
    book.memory_summary = compressed
    book.updated_at = get_china_now()
    db.commit()
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse(request, "partials/memory_summary.html", {"book": book})


@router.post("/update-style", response_class=HTMLResponse)
async def update_style(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    form = await request.form()
    book.style = form.get("style", "")
    book.updated_at = get_china_now()
    db.commit()
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse(request, "partials/style_summary.html", {"book": book})
