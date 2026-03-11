import logging

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Book, Chapter, GlobalConfig
from app.services.ai_service import AiService
from app.config import settings as app_settings
from app.utils.config_helper import get_global_config_dict

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
        new_summary = await ai_service.update_summary(book, full_text)
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
    db.commit()
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse(request, "partials/memory_summary.html", {"book": book})


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
    db.commit()
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse(request, "partials/style_summary.html", {"book": book})
