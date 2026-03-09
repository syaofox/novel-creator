from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
import re

from app.database import get_db
from app.models import Book, Chapter
from app.services.ai_service import AiService
from app.services.file_service import save_chapter, get_prev_ending
from app.config import settings as app_settings
from app.utils.helpers import extract_title

router = APIRouter(prefix="/books/{book_id}/chapters", tags=["chapters"])

@router.get("/write", response_class=HTMLResponse)
async def write_chapter_form(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    next_chapter = book.current_chapter + 1
    prev_ending = get_prev_ending(book_id, next_chapter)  # 获取上一章结尾（如果有）
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("write_chapter.html", {
        "request": request,
        "book": book,
        "chapter_number": next_chapter,
        "prev_ending": prev_ending
    })

@router.post("/", response_class=HTMLResponse)
async def generate_chapter(
    request: Request,
    book_id: int,
    core_event: str = Form(...),
    db: Session = Depends(get_db)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    next_chapter = book.current_chapter + 1
    prev_ending = get_prev_ending(book_id, next_chapter)

    ai_service = AiService(api_key=app_settings.deepseek_api_key, base_url=app_settings.deepseek_base_url)
    try:
        content = await ai_service.write_chapter(book, next_chapter, core_event, prev_ending)
    except Exception as e:
        # 返回错误信息，可显示在片段中
        return HTMLResponse(content=f"生成失败: {str(e)}", status_code=500)

    # 保存章节
    title = extract_title(content) or f"第{next_chapter}章"
    save_chapter(book_id, next_chapter, content)
    # 创建章节记录
    chapter = Chapter(book_id=book_id, chapter_number=next_chapter, title=title)
    db.add(chapter)
    # 更新当前章节数
    book.current_chapter = next_chapter
    db.commit()

    # 返回成功片段，包含预览和“更新摘要”按钮
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("partials/chapter_generated.html", {
        "request": request,
        "book": book,
        "chapter": chapter,
        "content": content[:500] + "..."  # 预览
    })

@router.get("/{chapter_num}", response_class=HTMLResponse)
async def read_chapter(request: Request, book_id: int, chapter_num: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    chapter = db.query(Chapter).filter(Chapter.book_id == book_id, Chapter.chapter_number == chapter_num).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    from app.services.file_service import read_chapter
    content = read_chapter(book_id, chapter_num)
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("chapter_view.html", {
        "request": request,
        "book": book,
        "chapter": chapter,
        "content": content
    })