import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, StreamingResponse

from app.config import settings as app_settings
from app.core.dependencies import RepoDep
from app.repositories.file_repository import (
    FileRepository,
    Book,
    Chapter,
    GlobalConfig,
    PlotSummary,
    CharacterCard,
    WritingStyle,
    MaterialNote,
    BookInitData,
)
from app.services.ai_service import AiService
from app.services.agents import InitBookAgent
from app.services.file_service import delete_book_files
from app.utils.config_helper import get_global_config_dict
from app.utils.helpers import get_book_dir, get_templates
from app.utils.json_helper import parse_chapter_titles, parse_init_data_markers
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


def _get_global_config(repo: FileRepository) -> dict:
    config = repo.get_global_config()
    return {
        "jailbreak_prefix": config.jailbreak_prefix or DEFAULT_JAILBREAK_PREFIX,
        "system_template": config.system_template or DEFAULT_SYSTEM_TEMPLATE,
        "temperature": config.temperature if config.temperature is not None else DEFAULT_TEMPERATURE,
        "top_p": config.top_p if config.top_p is not None else DEFAULT_TOP_P,
        "max_tokens": config.max_tokens if config.max_tokens is not None else DEFAULT_MAX_TOKENS,
        "stream": config.stream if config.stream is not None else DEFAULT_STREAM,
    }


def _all_materials(repo: FileRepository):
    return {
        "plot_summaries": [{"id": p.id, "title": p.title, "content": p.content} for p in repo.get_plot_summaries()],
        "character_cards": [{"id": c.id, "title": c.title, "content": c.content} for c in repo.get_character_cards()],
        "writing_styles": [
            {"id": w.id, "title": w.title, "content": w.content, "is_default": w.is_default}
            for w in repo.get_writing_styles()
        ],
        "material_notes": [{"id": n.id, "title": n.title, "content": n.content} for n in repo.get_material_notes()],
        "book_init_data": [
            {"id": d.id, "title": d.title, "content": d.content, "book_title": d.book_title}
            for d in repo.get_book_init_data_list()
        ],
    }


@router.get("/new", response_class=HTMLResponse)
async def new_book_form(request: Request, repo: RepoDep):
    gc = _get_global_config(repo)
    mats = _all_materials(repo)

    templates = get_templates()
    return templates.TemplateResponse(
        request,
        "new_book.html",
        {
            **gc,
            "default_style": DEFAULT_STYLE,
            "style_presets": STYLE_PRESETS,
            "genre_options": GENRE_OPTIONS,
            **mats,
        },
    )


def get_preview_params(
    request: Request,
    repo: FileRepository,
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
):
    gc = repo.get_global_config()
    if temperature == DEFAULT_TEMPERATURE and gc.temperature is not None:
        temperature = gc.temperature
    if top_p == DEFAULT_TOP_P and gc.top_p is not None:
        top_p = gc.top_p
    if max_tokens == DEFAULT_MAX_TOKENS and gc.max_tokens is not None:
        max_tokens = gc.max_tokens
    if stream == DEFAULT_STREAM and gc.stream is not None:
        stream = gc.stream
    if not jailbreak_prefix and gc.jailbreak_prefix:
        jailbreak_prefix = gc.jailbreak_prefix
    if system_template == DEFAULT_SYSTEM_TEMPLATE and gc.system_template:
        system_template = gc.system_template

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
    repo: RepoDep,
    title: str = Form(""),
    genre: str = Form(""),
    target_chapters: int = Form(3),
    basic_idea: str = Form(""),
    temperature: float = Form(DEFAULT_TEMPERATURE),
    top_p: float = Form(DEFAULT_TOP_P),
    max_tokens: int = Form(DEFAULT_MAX_TOKENS),
    stream: str = Form("true"),
    jailbreak_prefix: str = Form(""),
    system_template: str = Form(DEFAULT_SYSTEM_TEMPLATE),
    style: str = Form(""),
    init_data: str = Form(""),
):
    stream_bool = stream.lower() in ("true", "1", "on")
    genre_list = genre.split(",") if genre else []
    params = get_preview_params(
        request, repo, title, genre_list, target_chapters,
        basic_idea, temperature, top_p, max_tokens, stream_bool,
        jailbreak_prefix, system_template, style, init_data,
    )
    templates = get_templates()
    return templates.TemplateResponse(request, "book_preview.html", params)


@router.post("/init-stream")
async def init_book_stream(
    repo: RepoDep,
    basic_idea: str = Form(""),
    genre: str = Form(""),
    target_chapters: int = Form(3),
    jailbreak_prefix: str = Form(""),
    style: str = Form(""),
):
    global_config = get_global_config_dict(repo)

    async def generate():
        api_key = global_config.get("deepseek_api_key") or app_settings.deepseek_api_key
        base_url = global_config.get("deepseek_base_url") or app_settings.deepseek_base_url
        model = global_config.get("default_model") or app_settings.default_model
        ai_service = AiService(
            api_key=api_key,
            base_url=base_url,
            model=model,
            global_config=global_config,
        )
        agent = InitBookAgent(ai_service, global_config=global_config)
        agent.with_jailbreak(jailbreak_prefix).with_style(style)
        try:
            async for chunk in agent.stream_initialize(basic_idea, genre, target_chapters):
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
    repo: RepoDep,
    title: str = Form(...),
    genre: str = Form(default=""),
    target_chapters: int = Form(...),
    plot_summary: str = Form(""),
    character_card: str = Form(""),
    notes: str = Form(""),
    temperature: float = Form(DEFAULT_TEMPERATURE),
    top_p: float = Form(DEFAULT_TOP_P),
    max_tokens: int = Form(DEFAULT_MAX_TOKENS),
    stream: str = Form("true"),
    jailbreak_prefix: str = Form(DEFAULT_JAILBREAK_PREFIX),
    system_template: str = Form(DEFAULT_SYSTEM_TEMPLATE),
    style: str = Form(""),
    characters: str = Form(""),
    world_view: str = Form(""),
    outline: str = Form(""),
    foreshadowing: str = Form(""),
    other: str = Form(""),
):
    genre_str = genre if genre else ""
    stream_bool = stream.lower() in ("true", "1", "on")

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
        "stream": stream_bool,
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

    new_book = repo.create_book(Book(
        id=0,
        title=title,
        genre=genre_str,
        target_chapters=target_chapters,
        basic_idea=basic_idea,
        config=config,
        memory_summary=memory_summary,
        style=final_style,
        current_chapter=0,
    ))

    chapter_data = parse_chapter_titles(outline, target_chapters)
    for ch in chapter_data:
        repo.create_chapter(
            book_id=new_book.id,
            chapter_number=ch["chapter"],
            title=ch["title"],
            core_event=ch.get("core_event", ""),
        )

    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        chapters = repo.get_chapters(new_book.id)
        templates = get_templates()
        return templates.TemplateResponse(request, "book_detail.html", {"book": new_book, "chapters": chapters})

    return RedirectResponse(url=f"/books/{new_book.id}", status_code=303)


@router.get("/{book_id}", response_class=HTMLResponse)
async def book_detail(request: Request, book_id: int, repo: RepoDep):
    book = repo.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    chapters = repo.get_chapters(book_id)
    templates = get_templates()
    return templates.TemplateResponse(request, "book_detail.html", {"book": book, "chapters": chapters})


@router.post("/{book_id}/delete")
async def delete_book(book_id: int, repo: RepoDep):
    book = repo.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    repo.delete_book(book_id)
    delete_book_files(book_id)

    return RedirectResponse(url="/", status_code=303)


@router.get("/{book_id}/export")
async def export_book(book_id: int, repo: RepoDep):
    book = repo.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")

    book_dir = get_book_dir(book_id)
    export_dir = book_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    export_path = export_dir / f"{book.title}_完整版.txt"
    with open(export_path, "w", encoding="utf-8") as outfile:
        outfile.write(f"《{book.title}》\n\n")
        chapters = repo.get_chapters(book_id)
        for ch in chapters:
            outfile.write(f"第{ch.chapter_number}章 {ch.title}\n\n")
            outfile.write(str(ch.content or ""))
            outfile.write("\n\n")
    return FileResponse(path=export_path, filename=f"{book.title}.txt", media_type="text/plain")


@router.post("/{book_id}/finish")
async def finish_book(book_id: int, repo: RepoDep):
    book = repo.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    book.status = "已完结"
    repo.update_book(book)
    return RedirectResponse(url=f"/books/{book_id}", status_code=303)


@router.post("/{book_id}/unfinish")
async def unfinish_book(request: Request, book_id: int, repo: RepoDep):
    book = repo.get_book(book_id)
    if book:
        book.status = "进行中"
        repo.update_book(book)

    books = repo.get_books(status="已完结")
    return get_templates().TemplateResponse(request, "partials/book_list.html", {"books": books, "status": "已完结"})
