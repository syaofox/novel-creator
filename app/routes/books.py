import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.database import get_db
from app.models import Book, Chapter, GlobalConfig
from app.services.ai_service import AiService
from app.services.file_service import delete_book_files
from app.utils.config_helper import get_global_config_dict
from app.utils.helpers import get_book_dir
from app.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_MAX_TOKENS,
    DEFAULT_STREAM,
    DEFAULT_JAILBREAK_PREFIX,
    DEFAULT_SYSTEM_TEMPLATE,
    DEFAULT_STYLE,
    DEFAULT_MODEL,
    STYLE_PRESETS,
    TEMPLATE_DIR,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["books"])


def parse_chapter_titles(outline: str, target_chapters: int) -> list[dict]:
    """从大纲中解析章节信息,返回 [{chapter, title, core_event}, ...]"""

    def truncate_title(title: str, max_length: int = 50) -> str:
        if len(title) > max_length:
            return title[:max_length].strip() + "..."
        return title

    chapters = []

    try:
        data = json.loads(outline)
        if isinstance(data, dict) and "outline" in data:
            data = data["outline"]
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    title = item.get("title", "")
                    if not title:
                        title = f"第{len(chapters) + 1}章"
                    title = truncate_title(title)
                    core_event = item.get("core_event", "")
                    if not isinstance(core_event, str):
                        core_event = str(core_event) if core_event else ""
                    chapters.append(
                        {"chapter": item.get("chapter", len(chapters) + 1), "title": title, "core_event": core_event}
                    )
    except json.JSONDecodeError:
        lines = outline.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r"^(?:第\s*(\d+)\s*章|(\d+)[:、.]\s*)(.+)$", line)
            if match:
                num = int(match.group(1) or match.group(2))
                title = truncate_title(match.group(3).strip())
                chapters.append({"chapter": num, "title": title, "core_event": ""})
            elif chapters or line:
                chapters.append({"chapter": len(chapters) + 1, "title": truncate_title(line), "core_event": ""})

    while len(chapters) < target_chapters:
        chapters.append({"chapter": len(chapters) + 1, "title": f"第{len(chapters) + 1}章", "core_event": ""})

    return chapters[:target_chapters]


@router.get("/new", response_class=HTMLResponse)
async def new_book_form(request: Request, db: Session = Depends(get_db)):
    from fastapi.templating import Jinja2Templates

    config = db.query(GlobalConfig).filter(GlobalConfig.id == 1).first()
    if config:
        jailbreak_prefix = config.jailbreak_prefix
        system_template = config.system_template
        temperature = float(str(config.temperature))
        top_p = float(str(config.top_p))
        max_tokens = int(config.max_tokens)  # type: ignore
        stream = bool(config.stream)
    else:
        jailbreak_prefix = DEFAULT_JAILBREAK_PREFIX
        system_template = DEFAULT_SYSTEM_TEMPLATE
        temperature = DEFAULT_TEMPERATURE
        top_p = DEFAULT_TOP_P
        max_tokens = DEFAULT_MAX_TOKENS
        stream = DEFAULT_STREAM

    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    return templates.TemplateResponse(
        request,
        "new_book.html",
        {
            "jailbreak_prefix": jailbreak_prefix,
            "system_template": system_template,
            "default_temperature": temperature,
            "default_top_p": top_p,
            "default_max_tokens": max_tokens,
            "default_stream": stream,
            "default_style": DEFAULT_STYLE,
            "style_presets": STYLE_PRESETS,
        },
    )


@router.get("/preview", response_class=HTMLResponse)
async def preview_book(
    request: Request,
    title: str = "",
    genre: str = "",
    target_chapters: int = 30,
    basic_idea: str = "",
    temperature: float = DEFAULT_TEMPERATURE,
    top_p: float = DEFAULT_TOP_P,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    stream: bool = DEFAULT_STREAM,
    jailbreak_prefix: str = "",
    system_template: str = DEFAULT_SYSTEM_TEMPLATE,
    style: str = "",
    db: Session = Depends(get_db),
):
    # 获取全局配置默认值
    config = db.query(GlobalConfig).filter(GlobalConfig.id == 1).first()
    if config:
        # 如果参数等于常量默认值或为空，使用全局配置值
        if temperature == DEFAULT_TEMPERATURE:
            temperature = float(str(config.temperature))
        if top_p == DEFAULT_TOP_P:
            top_p = float(str(config.top_p))
        if max_tokens == DEFAULT_MAX_TOKENS:
            max_tokens = int(config.max_tokens)  # type: ignore
        if stream == DEFAULT_STREAM:
            stream = bool(config.stream)  # type: ignore
        if not jailbreak_prefix:
            jailbreak_prefix = str(config.jailbreak_prefix)
        if system_template == DEFAULT_SYSTEM_TEMPLATE:
            system_template = str(config.system_template)

    genre_str = genre if isinstance(genre, str) else ", ".join(genre) if genre else ""

    default_style = style or DEFAULT_STYLE

    chapter_list = [{"chapter": i + 1, "title": f"第{i + 1}章", "core_event": ""} for i in range(target_chapters)]

    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    return templates.TemplateResponse(
        request,
        "book_preview.html",
        {
            "title": title,
            "genre": genre_str,
            "target_chapters": target_chapters,
            "basic_idea": basic_idea,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": stream,
            "jailbreak_prefix": jailbreak_prefix,
            "system_template": system_template,
            "style": default_style,
            "style_presets": STYLE_PRESETS,
            "characters": "",
            "world_view": "",
            "outline": "",
            "foreshadowing": "",
            "other": "",
            "chapter_list": chapter_list,
        },
    )


@router.get("/init-stream")
async def init_book_stream(
    basic_idea: str = "",
    genre: str = "",
    target_chapters: int = 30,
    jailbreak_prefix: str = "",
    style: str = "",
    db: Session = Depends(get_db),
):
    """流式初始化小说,返回 SSE 格式的数据"""
    genre_str = genre if isinstance(genre, str) else ", ".join(genre) if genre else ""

    global_config = get_global_config_dict(db)

    async def generate():
        ai_service = AiService(
            api_key=app_settings.deepseek_api_key,
            base_url=app_settings.deepseek_base_url,
            model=global_config.get("default_model") or app_settings.default_model,
            global_config=global_config,
        )
        try:
            async for chunk in ai_service.stream_initialize_book(
                basic_idea, genre_str, target_chapters, jailbreak_prefix, style
            ):
                data = json.dumps(chunk, ensure_ascii=False)
                yield f"data: {data}\n\n"
                await asyncio.sleep(0.01)
            yield f"data: {json.dumps({'done': True})}\n\n"
        except TimeoutError:
            logger.error("Timeout during book initialization")
            yield f"data: {json.dumps({'error': '请求超时，请稍后重试'})}\n\n"
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during book initialization: {e}")
            yield f"data: {json.dumps({'error': '网络连接失败，请检查网络'})}\n\n"
        except Exception as e:
            logger.exception("Unexpected error during book initialization")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/", response_class=HTMLResponse)
async def create_book(
    request: Request,
    title: str = Form(...),
    genre: list[str] = Form(default=[]),
    target_chapters: int = Form(...),
    basic_idea: str = Form(...),
    temperature: float = Form(DEFAULT_TEMPERATURE),
    top_p: float = Form(DEFAULT_TOP_P),
    max_tokens: int = Form(DEFAULT_MAX_TOKENS),
    stream: bool = Form(DEFAULT_STREAM),
    jailbreak_prefix: str = Form(DEFAULT_JAILBREAK_PREFIX),
    system_template: str = Form(DEFAULT_SYSTEM_TEMPLATE),
    style: str = Form(""),
    characters: str = Form(""),
    world_view: str = Form(""),
    outline: str = Form(""),
    foreshadowing: str = Form(""),
    other: str = Form(""),
    db: Session = Depends(get_db),
):
    genre_str = ", ".join(genre) if genre else ""
    config = {
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": stream,
        "jailbreak_prefix": jailbreak_prefix,
        "system_template": system_template,
    }
    final_style = style

    memory_parts = [
        f"【人物卡】\n{characters}",
        f"【世界观】\n{world_view}",
        f"【风格规范】\n{final_style}",
        f"【主线进度】\n{outline}",
        f"【伏笔清单】\n{foreshadowing}",
        f"【其他信息】\n{other}",
    ]
    memory_summary = "\n\n".join(memory_parts)

    new_book = Book(
        title=title,
        genre=genre_str,
        target_chapters=target_chapters,
        basic_idea=basic_idea,
        config=config,
        memory_summary=memory_summary,
        style=final_style,
        current_chapter=0,
    )
    db.add(new_book)
    db.commit()
    db.refresh(new_book)

    chapter_data = parse_chapter_titles(outline, target_chapters)
    for ch in chapter_data:
        chapter = Chapter(
            book_id=new_book.id,
            chapter_number=ch["chapter"],
            title=ch["title"],
            core_event=ch.get("core_event", ""),
            status="未完成",
        )
        db.add(chapter)
    db.commit()

    return RedirectResponse(url=f"/books/{new_book.id}", status_code=303)


@router.get("/{book_id}", response_class=HTMLResponse)
async def book_detail(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    chapters = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_number).all()
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    return templates.TemplateResponse(request, "book_detail.html", {"book": book, "chapters": chapters})


@router.post("/{book_id}/delete")
async def delete_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    db.query(Chapter).filter(Chapter.book_id == book_id).delete()
    db.delete(book)
    db.commit()
    delete_book_files(book_id)

    return RedirectResponse(url="/", status_code=303)


@router.get("/{book_id}/export")
async def export_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    book_dir = get_book_dir(book_id)
    export_dir = book_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    # 合并所有章节
    export_path = export_dir / f"{book.title}_完整版.txt"
    with open(export_path, "w", encoding="utf-8") as outfile:
        outfile.write(f"《{book.title}》\n\n")
        chapters = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_number).all()
        for ch in chapters:
            outfile.write(f"第{ch.chapter_number}章 {ch.title}\n\n")
            outfile.write(str(ch.content or ""))
            outfile.write("\n\n")
    return FileResponse(path=export_path, filename=f"{book.title}.txt", media_type="text/plain")


@router.post("/{book_id}/finish")
async def finish_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if book:
        book.status = "已完结"  # type: ignore
        db.commit()
    return RedirectResponse(url=f"/books/{book_id}", status_code=303)
