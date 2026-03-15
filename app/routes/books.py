import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.database import get_db
from app.models import Book, Chapter, GlobalConfig, PlotSummary, CharacterCard, WritingStyle, MaterialNote, BookInitData
from app.services.ai_service import AiService
from app.services.file_service import delete_book_files
from app.utils.config_helper import get_global_config_dict
from app.utils.helpers import get_book_dir, get_templates
from app.utils.json_helper import parse_chapter_titles, parse_init_data_markers
from app.models import get_china_now
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
    GENRE_OPTIONS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/new", response_class=HTMLResponse)
async def new_book_form(request: Request, db: Session = Depends(get_db)):
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

    plot_summaries = [
        {"id": p.id, "title": p.title, "content": p.content}
        for p in db.query(PlotSummary).order_by(PlotSummary.updated_at.desc()).all()
    ]
    character_cards = [
        {"id": c.id, "title": c.title, "content": c.content}
        for c in db.query(CharacterCard).order_by(CharacterCard.updated_at.desc()).all()
    ]
    writing_styles = [
        {"id": w.id, "title": w.title, "content": w.content, "is_default": w.is_default}
        for w in db.query(WritingStyle).order_by(WritingStyle.is_default.desc(), WritingStyle.updated_at.desc()).all()
    ]
    material_notes = [
        {"id": n.id, "title": n.title, "content": n.content}
        for n in db.query(MaterialNote).order_by(MaterialNote.updated_at.desc()).all()
    ]
    book_init_data = [
        {"id": d.id, "title": d.title, "content": d.content, "book_title": d.book_title}
        for d in db.query(BookInitData).order_by(BookInitData.updated_at.desc()).all()
    ]

    templates = get_templates()
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
            "plot_summaries": plot_summaries,
            "character_cards": character_cards,
            "writing_styles": writing_styles,
            "material_notes": material_notes,
            "book_init_data": book_init_data,
            "genre_options": GENRE_OPTIONS,
        },
    )


def get_preview_params(
    request: Request,
    title: str = "",
    genre: list[str] | str = Query(default=[]),
    target_chapters: int = 3,
    basic_idea: str = "",
    temperature: float = DEFAULT_TEMPERATURE,
    top_p: float = DEFAULT_TOP_P,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    stream: bool = DEFAULT_STREAM,
    jailbreak_prefix: str = "",
    system_template: str = DEFAULT_SYSTEM_TEMPLATE,
    style: str = "",
    init_data: str = "",
    db: Session = Depends(get_db),
):
    config = db.query(GlobalConfig).filter(GlobalConfig.id == 1).first()
    if config:
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

    parsed_data: dict[str, Any] = {}
    raw_init_data = ""
    is_direct_input = bool(init_data and init_data.strip() and "【" in init_data)

    if init_data and init_data.strip():
        if is_direct_input:
            raw_init_data = init_data
            parsed_data = parse_init_data_markers(init_data)
        else:
            try:
                parsed_data = json.loads(init_data)
            except json.JSONDecodeError:
                if "【" in init_data and "】" in init_data:
                    parsed_data = parse_init_data_markers(init_data)

    characters = ""
    world_view = ""
    outline = ""
    foreshadowing = ""
    other = ""
    chapter_list = [{"chapter": i + 1, "title": f"第{i + 1}章", "core_event": ""} for i in range(target_chapters)]

    if parsed_data:
        if "characters" in parsed_data:
            characters = json.dumps(parsed_data["characters"], ensure_ascii=False)
        if "world_view" in parsed_data:
            world_view = json.dumps(parsed_data["world_view"], ensure_ascii=False)
        if "outline" in parsed_data:
            outline = json.dumps(parsed_data["outline"], ensure_ascii=False)
            if parsed_data["outline"]:
                chapter_list = [
                    {
                        "chapter": ch.get("chapter", i + 1),
                        "title": ch.get("title", f"第{i + 1}章"),
                        "core_event": ch.get("core_event", ""),
                    }
                    for i, ch in enumerate(parsed_data["outline"])
                ]
                target_chapters = len(chapter_list)
        if "foreshadowing" in parsed_data:
            foreshadowing = json.dumps(parsed_data["foreshadowing"], ensure_ascii=False)
        if "other" in parsed_data:
            other = json.dumps(parsed_data["other"], ensure_ascii=False)
            if isinstance(parsed_data["other"], dict) and parsed_data["other"].get("novel_title"):
                title = parsed_data["other"]["novel_title"]

    return {
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
        "characters": characters,
        "world_view": world_view,
        "outline": outline,
        "foreshadowing": foreshadowing,
        "other": other,
        "chapter_list": chapter_list,
        "raw_init_data": raw_init_data,
    }


@router.post("/preview", response_class=HTMLResponse)
async def preview_book(
    request: Request,
    title: str = Form(""),
    genre: str = Form(""),
    target_chapters: int = Form(3),
    basic_idea: str = Form(""),
    temperature: float = Form(DEFAULT_TEMPERATURE),
    top_p: float = Form(DEFAULT_TOP_P),
    max_tokens: int = Form(DEFAULT_MAX_TOKENS),
    stream: bool = Form(DEFAULT_STREAM),
    jailbreak_prefix: str = Form(""),
    system_template: str = Form(DEFAULT_SYSTEM_TEMPLATE),
    style: str = Form(""),
    init_data: str = Form(""),
    db: Session = Depends(get_db),
):
    genre_list = genre.split(",") if genre else []
    params = get_preview_params(
        request,
        title,
        genre_list,
        target_chapters,
        basic_idea,
        temperature,
        top_p,
        max_tokens,
        stream,
        jailbreak_prefix,
        system_template,
        style,
        init_data,
        db,
    )

    templates = get_templates()
    return templates.TemplateResponse(request, "book_preview.html", params)


@router.post("/init-stream")
async def init_book_stream(
    basic_idea: str = Form(""),
    genre: str = Form(""),
    target_chapters: int = Form(3),
    jailbreak_prefix: str = Form(""),
    style: str = Form(""),
    db: Session = Depends(get_db),
):
    """流式初始化小说,返回 ndjson 格式的流式响应"""

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
                basic_idea, genre, target_chapters, jailbreak_prefix, style
            ):
                data = json.dumps(chunk, ensure_ascii=False)
                yield f"{data}\n"
                await asyncio.sleep(0.01)
            yield json.dumps({"done": True}) + "\n"
        except TimeoutError:
            logger.error("Timeout during book initialization")
            yield json.dumps({"error": "请求超时，请稍后重试"}) + "\n"
        except (OSError, ConnectionError) as e:
            logger.error(f"Network error during book initialization: {e}")
            yield json.dumps({"error": "网络连接失败，请检查网络"}) + "\n"
        except Exception as e:
            logger.exception("Unexpected error during book initialization")
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.post("/", response_class=HTMLResponse)
async def create_book(
    request: Request,
    title: str = Form(...),
    genre: str = Form(default=""),
    target_chapters: int = Form(...),
    plot_summary: str = Form(""),
    character_card: str = Form(""),
    notes: str = Form(""),
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
    genre_str = genre if genre else ""

    basic_idea_parts = [
        f"剧情梗概: {plot_summary}" if plot_summary else "",
        f"人物卡: {character_card}" if character_card else "",
        f"注意事项: {notes}" if notes else "",
    ]
    basic_idea = "\n".join(filter(None, basic_idea_parts))
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

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        chapters = db.query(Chapter).filter(Chapter.book_id == new_book.id).order_by(Chapter.chapter_number).all()
        templates = get_templates()
        return templates.TemplateResponse(request, "book_detail.html", {"book": new_book, "chapters": chapters})

    return RedirectResponse(url=f"/books/{new_book.id}", status_code=303)


@router.get("/{book_id}", response_class=HTMLResponse)
async def book_detail(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    chapters = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_number).all()
    templates = get_templates()
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
        book.updated_at = get_china_now()
        db.commit()
    return RedirectResponse(url=f"/books/{book_id}", status_code=303)
