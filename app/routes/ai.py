from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Book
from app.services.ai_service import AiService
from app.config import settings as app_settings
from app.services.file_service import get_all_chapters_text
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/books/{book_id}/ai", tags=["ai"])

@router.post("/update-summary", response_class=HTMLResponse)
async def update_summary(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    # 获取所有章节全文（或者只获取新章节？这里简单获取全部）
    full_text = get_all_chapters_text(book_id)
    ai_service = AiService(api_key=app_settings.deepseek_api_key, base_url=app_settings.deepseek_base_url)
    try:
        new_summary = await ai_service.update_summary(book, full_text)
    except Exception as e:
        return HTMLResponse(content=f"更新摘要失败: {str(e)}", status_code=500)
    book.memory_summary = new_summary
    db.commit()
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("partials/memory_summary.html", {"request": request, "book": book})

@router.get("/global-review", response_class=HTMLResponse)
async def global_review(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    ai_service = AiService(api_key=app_settings.deepseek_api_key, base_url=app_settings.deepseek_base_url)
    try:
        review_result = await ai_service.global_review(book)
    except Exception as e:
        return HTMLResponse(content=f"回顾失败: {str(e)}", status_code=500)
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("partials/review_result.html", {"request": request, "review": review_result})

@router.post("/compress-summary", response_class=HTMLResponse)
async def compress_summary(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    ai_service = AiService(api_key=app_settings.deepseek_api_key, base_url=app_settings.deepseek_base_url)
    try:
        compressed = await ai_service.compress_summary(book)
    except Exception as e:
        return HTMLResponse(content=f"压缩摘要失败: {str(e)}", status_code=500)
    book.memory_summary = compressed
    db.commit()
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("partials/memory_summary.html", {"request": request, "book": book})