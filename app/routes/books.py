from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session
import os
import json
from pathlib import Path

from app.database import get_db
from app.models import Book, Chapter
from app.services.ai_service import AiService
from app.config import settings as app_settings
from app.utils.helpers import get_book_dir

router = APIRouter(prefix="/books", tags=["books"])

@router.get("/new", response_class=HTMLResponse)
async def new_book_form(request: Request):
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("new_book.html", {"request": request})

@router.post("/", response_class=HTMLResponse)
async def create_book(
    request: Request,
    title: str = Form(...),
    genre: str = Form(...),
    target_chapters: int = Form(...),
    basic_idea: str = Form(...),
    db: Session = Depends(get_db)
):
    # 创建书籍记录（先保存 basic_idea，config使用默认）
    new_book = Book(
        title=title,
        genre=genre,
        target_chapters=target_chapters,
        basic_idea=basic_idea,
        config=Book.__table__.c.config.default.arg  # 使用默认值
    )
    db.add(new_book)
    db.commit()
    db.refresh(new_book)

    # 异步调用 AI 初始化（这里为了简化，直接同步调用，实际可放入后台任务）
    ai_service = AiService(api_key=app_settings.deepseek_api_key, base_url=app_settings.deepseek_base_url)
    try:
        init_data = await ai_service.initialize_book(basic_idea, genre, target_chapters)
        # 将初始化结果合并到 memory_summary
        # init_data 应包含：人物卡、世界观、风格、大纲、初始摘要
        # 我们按6部分格式拼接：人物卡、世界观、风格、主线进度、伏笔、其他
        # 简单起见，将各部分用换行分隔
        memory_parts = [
            f"【人物卡】\n{init_data.get('characters', '')}",
            f"【世界观】\n{init_data.get('world_view', '')}",
            f"【风格规范】\n{init_data.get('style', '')}",
            f"【主线进度】\n{init_data.get('outline', '')}",
            f"【伏笔清单】\n{init_data.get('foreshadowing', '')}",
            f"【其他信息】\n{init_data.get('other', '')}"
        ]
        new_book.memory_summary = "\n\n".join(memory_parts)
        # 也可以将大纲单独存储，但为了简化，放入 memory_summary
    except Exception as e:
        # 初始化失败，至少设置一个默认摘要
        new_book.memory_summary = f"初始化失败: {str(e)}，请稍后手动更新摘要。"
    db.commit()

    return RedirectResponse(url=f"/books/{new_book.id}", status_code=303)

@router.get("/{book_id}", response_class=HTMLResponse)
async def book_detail(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    chapters = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_number).all()
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("book_detail.html", {
        "request": request,
        "book": book,
        "chapters": chapters
    })

@router.get("/{book_id}/export")
async def export_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    book_dir = get_book_dir(book_id)
    chapters_dir = book_dir / "chapters"
    export_dir = book_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    # 合并所有章节
    export_path = export_dir / f"{book.title}_完整版.txt"
    with open(export_path, "w", encoding="utf-8") as outfile:
        outfile.write(f"《{book.title}》\n\n")
        chapters = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_number).all()
        for ch in chapters:
            chapter_file = chapters_dir / f"{ch.chapter_number}.txt"
            if chapter_file.exists():
                content = chapter_file.read_text(encoding="utf-8")
                outfile.write(f"第{ch.chapter_number}章 {ch.title}\n\n")
                outfile.write(content)
                outfile.write("\n\n")
    return FileResponse(path=export_path, filename=f"{book.title}.txt", media_type="text/plain")

@router.post("/{book_id}/finish")
async def finish_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if book:
        book.status = "已完结"
        db.commit()
    return RedirectResponse(url=f"/books/{book_id}", status_code=303)