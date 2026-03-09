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
async def write_chapter_form(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    next_chapter = int(book.current_chapter) + 1
    prev_ending = get_prev_ending(book_id, next_chapter)
    core_event = extract_chapter_outline(book.memory_summary, next_chapter)
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse(
        "write_chapter.html",
        {
            "request": request,
            "book": book,
            "chapter_number": next_chapter,
            "prev_ending": prev_ending,
            "core_event": core_event,
        },
    )


@router.post("/", response_class=HTMLResponse)
async def generate_chapter(request: Request, book_id: int, core_event: str = Form(...), db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    current = book.current_chapter or 0
    next_chapter = current + 1
    prev_ending = get_prev_ending(book_id, next_chapter)

    ai_service = AiService(api_key=app_settings.deepseek_api_key, base_url=app_settings.deepseek_base_url)
    try:
        content = await ai_service.write_chapter(book, next_chapter, core_event, prev_ending)
    except Exception as e:
        return HTMLResponse(content=f"生成失败: {str(e)}", status_code=500)

    title = extract_title(content) or f"第{next_chapter}章"
    try:
        save_chapter(book_id, next_chapter, content)
    except Exception as e:
        import traceback

        return HTMLResponse(content=f"保存章节失败: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status_code=500)
    try:
        chapter = Chapter(book_id=book_id, chapter_number=next_chapter, title=title)
        db.add(chapter)
        book.current_chapter = next_chapter
        db.commit()
    except Exception as e:
        import traceback

        return HTMLResponse(content=f"保存数据库失败: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status_code=500)

    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="app/templates")
    try:
        return templates.TemplateResponse(
            "partials/chapter_generated.html",
            {"request": request, "book": book, "chapter": chapter, "content": content[:500] + "..."},
        )
    except Exception as e:
        import traceback

        return HTMLResponse(content=f"模板渲染失败: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status_code=500)


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
    return templates.TemplateResponse(
        "chapter_view.html", {"request": request, "book": book, "chapter": chapter, "content": content}
    )
