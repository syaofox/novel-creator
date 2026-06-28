import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from app.core.dependencies import RepoDep, AiServiceDep
from app.constants import DEFAULT_STYLE
from app.utils.helpers import get_templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/materials", tags=["materials"])


def _materials_context(repo):
    from app.repositories.file_repository import BookInitData

    return {
        "plot_summaries": repo.get_plot_summaries(),
        "character_cards": repo.get_character_cards(),
        "writing_styles": repo.get_writing_styles(),
        "material_notes": repo.get_material_notes(),
        "book_init_data": repo.get_book_init_data_list(),
        "default_style": DEFAULT_STYLE,
    }


@router.get("", response_class=HTMLResponse)
async def materials_page(request: Request, repo: RepoDep, tab: str = Query(default="plot")):
    ctx = _materials_context(repo)
    ctx["active_tab"] = tab
    templates = get_templates()
    return templates.TemplateResponse(request, "materials.html", ctx)


@router.post("/plot-summaries", response_class=HTMLResponse)
async def create_plot_summary(
    request: Request, repo: RepoDep, title: str = Form(...), content: str = Form(""), source: str = Form(None)
):
    new_plot = repo.create_plot_summary(title=title, content=content)

    if source == "new_book":
        plots = repo.get_plot_summaries()
        templates = get_templates()
        response = templates.TemplateResponse(
            request,
            "partials/select_options.html",
            {"items": plots, "select_id": "plotSelect", "placeholder": "-- 选择已有剧情梗概 --"},
        )
        response.headers["X-New-Id"] = str(new_plot.id)
        return response

    return RedirectResponse(url="/materials", status_code=303)


@router.post("/plot-summaries/{plot_id}", response_class=HTMLResponse)
async def update_plot_summary(
    request: Request, plot_id: int, repo: RepoDep, title: str = Form(...), content: str = Form("")
):
    updated = repo.update_plot_summary(plot_id, title=title, content=content)
    if not updated:
        raise HTTPException(status_code=404, detail="剧情梗概不存在")
    return RedirectResponse(url="/materials", status_code=303)


@router.post("/plot-summaries/{plot_id}/delete", response_class=HTMLResponse)
async def delete_plot_summary(plot_id: int, repo: RepoDep):
    if not repo.delete_plot_summary(plot_id):
        raise HTTPException(status_code=404, detail="剧情梗概不存在")
    return RedirectResponse(url="/materials", status_code=303)


def extract_character_names(content: str) -> list[str]:
    if not content:
        return []
    import re

    names = []
    lines = content.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^([^:：]+)[:：]", line)
        if match:
            name = match.group(1).strip()
            if name and name not in names:
                names.append(name)
    return names


def generate_character_card_title(content: str) -> str:
    names = extract_character_names(content)
    if not names:
        return "未命名人物卡"
    if len(names) == 1:
        return names[0]
    if len(names) <= 3:
        return "、".join(names)
    return f"{names[0]}等{len(names)}人"


def split_characters(content: str) -> list[dict[str, str]]:
    if not content:
        return []
    import re

    sections = re.split(r"\n\s*\n", content.strip())
    characters = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        lines = section.split("\n")
        first_line = lines[0].strip() if lines else ""
        match = re.match(r"^([^:：]+)[:：]\s*(.*)$", first_line)

        if match:
            name = match.group(1).strip()
            first_line_content = match.group(2).strip()
            remaining_lines = lines[1:] if len(lines) > 1 else []
            all_content = [first_line_content] + remaining_lines if first_line_content else remaining_lines
            section = "\n".join(all_content).strip()
        else:
            names_in_section = extract_character_names(section)
            name = names_in_section[0] if names_in_section else "未命名"

        characters.append({"name": name, "content": section})

    return characters


@router.post("/character-cards/split-save", response_class=HTMLResponse)
async def split_save_character_cards(
    request: Request, repo: RepoDep, content: str = Form(...), confirm_overwrite: int = Form(0)
):
    characters = split_characters(content)
    duplicate_names = []

    if not characters:
        title = "未命名人物卡"
        if repo.get_character_card_by_title(title):
            duplicate_names.append(title)
    else:
        for char in characters:
            existing = repo.get_character_card_by_title(char["name"])
            if existing:
                duplicate_names.append(char["name"])

    if duplicate_names and not confirm_overwrite:
        templates = get_templates()
        return templates.TemplateResponse(
            request,
            "partials/split_save_modal_content.html",
            {
                "content": content,
                "duplicate_names": duplicate_names,
            },
        )

    saved_cards = []
    if not characters:
        card = repo.create_character_card(title="未命名人物卡", content=content)
        saved_cards = [{"id": card.id, "name": card.title}]
    else:
        for char in characters:
            card = repo.create_character_card(title=char["name"], content=char["content"])
            saved_cards.append({"id": card.id, "name": card.title})

    response = HTMLResponse(content=f'<input type="hidden" name="saved_count" value="{len(saved_cards)}">')
    response.headers["X-New-Ids"] = json.dumps(saved_cards)
    if duplicate_names:
        response.headers["X-Duplicate-Names"] = json.dumps(duplicate_names)
    return response


@router.post("/character-cards", response_class=HTMLResponse)
async def create_character_card(
    request: Request,
    repo: RepoDep,
    title: str = Form(""),
    content: str = Form(""),
    source: str = Form(None),
    auto_title: int = Form(0),
    confirm_overwrite: int = Form(0),
):
    if auto_title == 1 or not title.strip():
        title = generate_character_card_title(content)

    existing = repo.get_character_card_by_title(title)
    if existing and not confirm_overwrite:
        templates = get_templates()
        return templates.TemplateResponse(
            request,
            "partials/character_duplicate_warning.html",
            {"title": title, "content": content, "existing": existing, "source": source, "auto_title": auto_title},
        )

    card = repo.create_character_card(title=title, content=content)

    if source == "new_book":
        response = HTMLResponse(content=f'<input type="hidden" name="X-New-Id" value="{card.id}">')
        response.headers["X-New-Id"] = str(card.id)
        return response

    response = HTMLResponse("")
    response.headers["HX-Redirect"] = "/materials?tab=character"
    return response


@router.post("/character-cards/{card_id}", response_class=HTMLResponse)
async def update_character_card(
    request: Request,
    card_id: int,
    repo: RepoDep,
    title: str = Form(...),
    content: str = Form(""),
    confirm_overwrite: int = Form(0),
):
    card = repo.get_character_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="人物卡不存在")

    existing = repo.get_character_card_by_title(title)
    if existing and existing.id != card_id and not confirm_overwrite:
        templates = get_templates()
        return templates.TemplateResponse(
            request,
            "partials/edit_modal.html",
            {
                "item": card,
                "item_type": "character",
                "action_url": f"/materials/character-cards/{card_id}",
                "duplicate_warning": {"title": title, "content": content, "existing_title": existing.title},
            },
        )

    repo.update_character_card(card_id, title=title, content=content)
    response = HTMLResponse("")
    response.headers["HX-Redirect"] = "/materials?tab=character"
    return response


@router.post("/character-cards/{card_id}/delete", response_class=HTMLResponse)
async def delete_character_card(card_id: int, repo: RepoDep):
    if not repo.delete_character_card(card_id):
        raise HTTPException(status_code=404, detail="人物卡不存在")
    return RedirectResponse(url="/materials?tab=character", status_code=303)


@router.post("/writing-styles/extract")
async def extract_writing_style(ai_service: AiServiceDep, text_snippet: str = Form(...)):
    from app.services.agents import AgentFactory

    agent = AgentFactory.create("style_extractor", ai_service, global_config=ai_service.global_config)

    try:
        result = await agent.extract_style(text_snippet)
        return {
            "title": result.get("title", ""),
            "content": result.get("content", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/writing-styles", response_class=HTMLResponse)
async def create_writing_style(
    request: Request,
    repo: RepoDep,
    title: str = Form(...),
    content: str = Form(""),
    is_default: int = Form(0),
    source: str = Form(None),
):
    if is_default == 1:
        for style in repo.get_writing_styles():
            if style.is_default:
                repo.update_writing_style(style.id, is_default=0)
    new_style = repo.create_writing_style(title=title, content=content, is_default=is_default)

    if source == "new_book":
        styles = repo.get_writing_styles()
        templates = get_templates()
        response = templates.TemplateResponse(
            request,
            "partials/select_options.html",
            {"items": styles, "select_id": "styleSelect", "placeholder": "-- 选择已有文风 --", "show_default": True},
        )
        response.headers["X-New-Id"] = str(new_style.id)
        return response

    return RedirectResponse(url="/materials?tab=style", status_code=303)


@router.post("/writing-styles/{style_id}", response_class=HTMLResponse)
async def update_writing_style(
    request: Request,
    style_id: int,
    repo: RepoDep,
    title: str = Form(...),
    content: str = Form(""),
    is_default: int = Form(0),
):
    existing = repo.get_writing_style(style_id)
    if not existing:
        raise HTTPException(status_code=404, detail="文风不存在")
    if is_default == 1:
        for style in repo.get_writing_styles():
            if style.id != style_id and style.is_default:
                repo.update_writing_style(style.id, is_default=0)
    repo.update_writing_style(style_id, title=title, content=content, is_default=is_default)
    return RedirectResponse(url="/materials?tab=style", status_code=303)


@router.post("/writing-styles/{style_id}/delete", response_class=HTMLResponse)
async def delete_writing_style(style_id: int, repo: RepoDep):
    style = repo.get_writing_style(style_id)
    if not style:
        raise HTTPException(status_code=404, detail="文风不存在")
    if style.is_default == 1:
        raise HTTPException(status_code=400, detail="不能删除默认文风")
    repo.delete_writing_style(style_id)
    return RedirectResponse(url="/materials?tab=style", status_code=303)


@router.post("/material-notes", response_class=HTMLResponse)
async def create_material_note(
    request: Request, repo: RepoDep, title: str = Form(...), content: str = Form(""), source: str = Form(None)
):
    new_note = repo.create_material_note(title=title, content=content)

    if source == "new_book":
        notes = repo.get_material_notes()
        templates = get_templates()
        response = templates.TemplateResponse(
            request,
            "partials/select_options.html",
            {"items": notes, "select_id": "noteSelect", "placeholder": "-- 选择已有注意事项 --"},
        )
        response.headers["X-New-Id"] = str(new_note.id)
        return response

    return RedirectResponse(url="/materials?tab=note", status_code=303)


@router.post("/material-notes/{note_id}", response_class=HTMLResponse)
async def update_material_note(
    request: Request, note_id: int, repo: RepoDep, title: str = Form(...), content: str = Form("")
):
    updated = repo.update_material_note(note_id, title=title, content=content)
    if not updated:
        raise HTTPException(status_code=404, detail="注意事项不存在")
    return RedirectResponse(url="/materials?tab=note", status_code=303)


@router.post("/material-notes/{note_id}/delete", response_class=HTMLResponse)
async def delete_material_note(note_id: int, repo: RepoDep):
    if not repo.delete_material_note(note_id):
        raise HTTPException(status_code=404, detail="注意事项不存在")
    return RedirectResponse(url="/materials?tab=note", status_code=303)


@router.get("/partial", response_class=HTMLResponse)
async def get_materials_partial(request: Request, repo: RepoDep, tab: str = Query(default="plot")):
    is_htmx = request.headers.get("HX-Request") == "true"
    ctx = _materials_context(repo)
    ctx["active_tab"] = tab

    templates = get_templates()

    if is_htmx:
        return templates.TemplateResponse(request, "partials/materials_tabs.html", ctx)

    return templates.TemplateResponse(request, "materials.html", ctx)


@router.get("/plot-summaries/{plot_id}/edit", response_class=HTMLResponse)
async def edit_plot_summary_modal(request: Request, plot_id: int, repo: RepoDep):
    item = repo.get_plot_summary(plot_id)
    if not item:
        raise HTTPException(status_code=404, detail="剧情梗概不存在")
    templates = get_templates()
    return templates.TemplateResponse(
        "partials/edit_modal.html",
        {"request": request, "item": item, "item_type": "plot", "action_url": f"/materials/plot-summaries/{plot_id}"},
    )


@router.get("/character-cards/{card_id}/edit", response_class=HTMLResponse)
async def edit_character_card_modal(request: Request, card_id: int, repo: RepoDep):
    card = repo.get_character_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="人物卡不存在")
    templates = get_templates()
    return templates.TemplateResponse(
        "partials/edit_modal.html",
        {
            "request": request,
            "item": card,
            "item_type": "character",
            "action_url": f"/materials/character-cards/{card_id}",
        },
    )


@router.get("/material-notes/{note_id}/edit", response_class=HTMLResponse)
async def edit_material_note_modal(request: Request, note_id: int, repo: RepoDep):
    note = repo.get_material_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="注意事项不存在")
    templates = get_templates()
    return templates.TemplateResponse(
        "partials/edit_modal.html",
        {"request": request, "item": note, "item_type": "note", "action_url": f"/materials/material-notes/{note_id}"},
    )


@router.get("/writing-styles/{style_id}/edit", response_class=HTMLResponse)
async def edit_writing_style_modal(request: Request, style_id: int, repo: RepoDep):
    style = repo.get_writing_style(style_id)
    if not style:
        raise HTTPException(status_code=404, detail="文风不存在")
    templates = get_templates()
    return templates.TemplateResponse(
        "partials/edit_modal.html",
        {
            "request": request,
            "item": style,
            "item_type": "style",
            "action_url": f"/materials/writing-styles/{style_id}",
            "show_default": True,
        },
    )


@router.post("/book-init-data", response_class=HTMLResponse)
async def create_book_init_data(
    request: Request, repo: RepoDep, title: str = Form(...), content: str = Form(""), book_title: str = Form("")
):
    repo.create_book_init_data(title=title, content=content, book_title=book_title)
    return RedirectResponse(url="/materials?tab=init", status_code=303)


@router.post("/book-init-data/{data_id}", response_class=HTMLResponse)
async def update_book_init_data(
    request: Request,
    data_id: int,
    repo: RepoDep,
    title: str = Form(...),
    content: str = Form(""),
    book_title: str = Form(""),
):
    updated = repo.update_book_init_data(data_id, title=title, content=content, book_title=book_title)
    if not updated:
        raise HTTPException(status_code=404, detail="初始化数据不存在")
    return RedirectResponse(url="/materials?tab=init", status_code=303)


@router.post("/book-init-data/{data_id}/delete", response_class=HTMLResponse)
async def delete_book_init_data(data_id: int, repo: RepoDep):
    if not repo.delete_book_init_data(data_id):
        raise HTTPException(status_code=404, detail="初始化数据不存在")
    return RedirectResponse(url="/materials?tab=init", status_code=303)


@router.get("/book-init-data/{data_id}/edit", response_class=HTMLResponse)
async def edit_book_init_data_modal(request: Request, data_id: int, repo: RepoDep):
    item = repo.get_book_init_data(data_id)
    if not item:
        raise HTTPException(status_code=404, detail="初始化数据不存在")
    templates = get_templates()
    return templates.TemplateResponse(
        "partials/edit_modal.html",
        {"request": request, "item": item, "item_type": "init", "action_url": f"/materials/book-init-data/{data_id}"},
    )
