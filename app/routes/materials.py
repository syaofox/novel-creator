import logging

from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PlotSummary, CharacterCard, WritingStyle, MaterialNote, BookInitData, get_china_now
from app.constants import DEFAULT_STYLE, TEMPLATE_DIR
from app.utils.helpers import get_templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("", response_class=HTMLResponse)
async def materials_page(request: Request, tab: str = Query(default="plot"), db: Session = Depends(get_db)):
    from fastapi.templating import Jinja2Templates

    plot_summaries = db.query(PlotSummary).order_by(PlotSummary.updated_at.desc()).all()
    character_cards = db.query(CharacterCard).order_by(CharacterCard.updated_at.desc()).all()
    writing_styles = (
        db.query(WritingStyle).order_by(WritingStyle.is_default.desc(), WritingStyle.updated_at.desc()).all()
    )
    material_notes = db.query(MaterialNote).order_by(MaterialNote.updated_at.desc()).all()
    book_init_data = db.query(BookInitData).order_by(BookInitData.updated_at.desc()).all()

    templates = get_templates()
    return templates.TemplateResponse(
        request,
        "materials.html",
        {
            "plot_summaries": plot_summaries,
            "character_cards": character_cards,
            "writing_styles": writing_styles,
            "material_notes": material_notes,
            "book_init_data": book_init_data,
            "default_style": DEFAULT_STYLE,
            "active_tab": tab,
        },
    )


@router.post("/plot-summaries", response_class=HTMLResponse)
async def create_plot_summary(
    request: Request,
    title: str = Form(...),
    content: str = Form(""),
    source: str = Form(None),
    db: Session = Depends(get_db),
):
    new_plot = PlotSummary(title=title, content=content)
    db.add(new_plot)
    db.commit()
    db.refresh(new_plot)

    if source == "new_book":
        plots = db.query(PlotSummary).order_by(PlotSummary.updated_at.desc()).all()
        from fastapi.templating import Jinja2Templates

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
    request: Request, plot_id: int, title: str = Form(...), content: str = Form(""), db: Session = Depends(get_db)
):
    plot = db.query(PlotSummary).filter(PlotSummary.id == plot_id).first()
    if not plot:
        raise HTTPException(status_code=404, detail="剧情梗概不存在")
    plot.title = title
    plot.content = content
    plot.updated_at = get_china_now()
    db.commit()
    return RedirectResponse(url="/materials", status_code=303)


@router.post("/plot-summaries/{plot_id}/delete", response_class=HTMLResponse)
async def delete_plot_summary(plot_id: int, db: Session = Depends(get_db)):
    plot = db.query(PlotSummary).filter(PlotSummary.id == plot_id).first()
    if not plot:
        raise HTTPException(status_code=404, detail="剧情梗概不存在")
    db.delete(plot)
    db.commit()
    return RedirectResponse(url="/materials", status_code=303)


def extract_character_names(content: str) -> list[str]:
    """从人物卡内容中提取人物名称列表"""
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
    """根据人物卡内容生成标题"""
    names = extract_character_names(content)
    if not names:
        return "未命名人物卡"
    if len(names) == 1:
        return names[0]
    if len(names) <= 3:
        return "、".join(names)
    return f"{names[0]}等{len(names)}人"


def split_characters(content: str) -> list[dict[str, str]]:
    """将人物卡内容拆分为多个单人物条目"""
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
async def split_save_character_cards(request: Request, content: str = Form(...), db: Session = Depends(get_db)):
    """将多人物内容拆分为独立的单人物卡并保存"""
    characters = split_characters(content)
    saved_cards = []

    if not characters:
        new_card = CharacterCard(title="未命名人物卡", content=content)
        db.add(new_card)
        db.commit()
        db.refresh(new_card)
        saved_cards = [{"id": new_card.id, "name": new_card.title}]
    else:
        cards = []
        for char in characters:
            card = CharacterCard(title=char["name"], content=char["content"])
            db.add(card)
            cards.append(card)
        db.commit()
        for card in cards:
            db.refresh(card)
            saved_cards.append({"id": card.id, "name": card.title})

    from fastapi.responses import HTMLResponse
    import json

    response = HTMLResponse(content=f'<input type="hidden" name="saved_count" value="{len(saved_cards)}">')
    response.headers["X-New-Ids"] = json.dumps(saved_cards)
    return response


@router.post("/character-cards", response_class=HTMLResponse)
async def create_character_card(
    request: Request,
    title: str = Form(""),
    content: str = Form(""),
    source: str = Form(None),
    auto_title: int = Form(0),
    db: Session = Depends(get_db),
):
    if auto_title == 1 or not title.strip():
        title = generate_character_card_title(content)

    new_card = CharacterCard(title=title, content=content)
    db.add(new_card)
    db.commit()
    db.refresh(new_card)

    if source == "new_book":
        from fastapi.responses import HTMLResponse

        response = HTMLResponse(content=f'<input type="hidden" name="X-New-Id" value="{new_card.id}">')
        response.headers["X-New-Id"] = str(new_card.id)
        return response

    return RedirectResponse(url="/materials?tab=character", status_code=303)


@router.post("/character-cards/{card_id}", response_class=HTMLResponse)
async def update_character_card(
    request: Request, card_id: int, title: str = Form(...), content: str = Form(""), db: Session = Depends(get_db)
):
    card = db.query(CharacterCard).filter(CharacterCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="人物卡不存在")
    card.title = title
    card.content = content
    card.updated_at = get_china_now()
    db.commit()
    return RedirectResponse(url="/materials?tab=character", status_code=303)


@router.post("/character-cards/{card_id}/delete", response_class=HTMLResponse)
async def delete_character_card(card_id: int, db: Session = Depends(get_db)):
    card = db.query(CharacterCard).filter(CharacterCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="人物卡不存在")
    db.delete(card)
    db.commit()
    return RedirectResponse(url="/materials?tab=character", status_code=303)


@router.post("/writing-styles", response_class=HTMLResponse)
async def create_writing_style(
    request: Request,
    title: str = Form(...),
    content: str = Form(""),
    is_default: int = Form(0),
    source: str = Form(None),
    db: Session = Depends(get_db),
):
    if is_default == 1:
        db.query(WritingStyle).update({"is_default": 0})
    new_style = WritingStyle(title=title, content=content, is_default=is_default)
    db.add(new_style)
    db.commit()
    db.refresh(new_style)

    if source == "new_book":
        styles = db.query(WritingStyle).order_by(WritingStyle.is_default.desc(), WritingStyle.updated_at.desc()).all()
        from fastapi.templating import Jinja2Templates

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
    title: str = Form(...),
    content: str = Form(""),
    is_default: int = Form(0),
    db: Session = Depends(get_db),
):
    style = db.query(WritingStyle).filter(WritingStyle.id == style_id).first()
    if not style:
        raise HTTPException(status_code=404, detail="文风不存在")
    if is_default == 1:
        db.query(WritingStyle).filter(WritingStyle.id != style_id).update({"is_default": 0})
    style.title = title
    style.content = content
    style.is_default = is_default
    style.updated_at = get_china_now()
    db.commit()
    return RedirectResponse(url="/materials?tab=style", status_code=303)


@router.post("/writing-styles/{style_id}/delete", response_class=HTMLResponse)
async def delete_writing_style(style_id: int, db: Session = Depends(get_db)):
    style = db.query(WritingStyle).filter(WritingStyle.id == style_id).first()
    if not style:
        raise HTTPException(status_code=404, detail="文风不存在")
    if style.is_default == 1:
        raise HTTPException(status_code=400, detail="不能删除默认文风")
    db.delete(style)
    db.commit()
    return RedirectResponse(url="/materials?tab=style", status_code=303)


@router.post("/material-notes", response_class=HTMLResponse)
async def create_material_note(
    request: Request,
    title: str = Form(...),
    content: str = Form(""),
    source: str = Form(None),
    db: Session = Depends(get_db),
):
    new_note = MaterialNote(title=title, content=content)
    db.add(new_note)
    db.commit()
    db.refresh(new_note)

    if source == "new_book":
        notes = db.query(MaterialNote).order_by(MaterialNote.updated_at.desc()).all()
        from fastapi.templating import Jinja2Templates

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
    request: Request, note_id: int, title: str = Form(...), content: str = Form(""), db: Session = Depends(get_db)
):
    note = db.query(MaterialNote).filter(MaterialNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="注意事项不存在")
    note.title = title
    note.content = content
    note.updated_at = get_china_now()
    db.commit()
    return RedirectResponse(url="/materials?tab=note", status_code=303)


@router.post("/material-notes/{note_id}/delete", response_class=HTMLResponse)
async def delete_material_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(MaterialNote).filter(MaterialNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="注意事项不存在")
    db.delete(note)
    db.commit()
    return RedirectResponse(url="/materials?tab=note", status_code=303)


@router.get("/partial", response_class=HTMLResponse)
async def get_materials_partial(request: Request, tab: str = Query(default="plot"), db: Session = Depends(get_db)):
    """htmx 片段路由，返回带有指定tab激活状态的内容"""
    is_htmx = request.headers.get("HX-Request") == "true"
    from fastapi.templating import Jinja2Templates

    plot_summaries = db.query(PlotSummary).order_by(PlotSummary.updated_at.desc()).all()
    character_cards = db.query(CharacterCard).order_by(CharacterCard.updated_at.desc()).all()
    writing_styles = (
        db.query(WritingStyle).order_by(WritingStyle.is_default.desc(), WritingStyle.updated_at.desc()).all()
    )
    material_notes = db.query(MaterialNote).order_by(MaterialNote.updated_at.desc()).all()
    book_init_data = db.query(BookInitData).order_by(BookInitData.updated_at.desc()).all()

    templates = get_templates()

    if is_htmx:
        return templates.TemplateResponse(
            request,
            "partials/materials_tabs.html",
            {
                "plot_summaries": plot_summaries,
                "character_cards": character_cards,
                "writing_styles": writing_styles,
                "material_notes": material_notes,
                "book_init_data": book_init_data,
                "default_style": DEFAULT_STYLE,
                "active_tab": tab,
            },
        )

    return templates.TemplateResponse(
        request,
        "materials.html",
        {
            "plot_summaries": plot_summaries,
            "character_cards": character_cards,
            "writing_styles": writing_styles,
            "material_notes": material_notes,
            "book_init_data": book_init_data,
            "default_style": DEFAULT_STYLE,
            "active_tab": tab,
        },
    )


@router.get("/plot-summaries/{plot_id}/edit", response_class=HTMLResponse)
async def edit_plot_summary_modal(request: Request, plot_id: int, db: Session = Depends(get_db)):
    """返回编辑剧情梗概的模态框"""
    plot = db.query(PlotSummary).filter(PlotSummary.id == plot_id).first()
    if not plot:
        raise HTTPException(status_code=404, detail="剧情梗概不存在")

    from fastapi.templating import Jinja2Templates

    templates = get_templates()
    return templates.TemplateResponse(
        "partials/edit_modal.html",
        {"request": request, "item": plot, "item_type": "plot", "action_url": f"/materials/plot-summaries/{plot_id}"},
    )


@router.get("/character-cards/{card_id}/edit", response_class=HTMLResponse)
async def edit_character_card_modal(request: Request, card_id: int, db: Session = Depends(get_db)):
    """返回编辑人物卡的模态框"""
    card = db.query(CharacterCard).filter(CharacterCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="人物卡不存在")

    from fastapi.templating import Jinja2Templates

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
async def edit_material_note_modal(request: Request, note_id: int, db: Session = Depends(get_db)):
    """返回编辑注意事项的模态框"""
    note = db.query(MaterialNote).filter(MaterialNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="注意事项不存在")

    from fastapi.templating import Jinja2Templates

    templates = get_templates()
    return templates.TemplateResponse(
        "partials/edit_modal.html",
        {"request": request, "item": note, "item_type": "note", "action_url": f"/materials/material-notes/{note_id}"},
    )


@router.get("/writing-styles/{style_id}/edit", response_class=HTMLResponse)
async def edit_writing_style_modal(request: Request, style_id: int, db: Session = Depends(get_db)):
    """返回编辑文风的模态框"""
    style = db.query(WritingStyle).filter(WritingStyle.id == style_id).first()
    if not style:
        raise HTTPException(status_code=404, detail="文风不存在")

    from fastapi.templating import Jinja2Templates

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
    request: Request,
    title: str = Form(...),
    content: str = Form(""),
    book_title: str = Form(""),
    db: Session = Depends(get_db),
):
    new_data = BookInitData(title=title, content=content, book_title=book_title)
    db.add(new_data)
    db.commit()
    return RedirectResponse(url="/materials?tab=init", status_code=303)


@router.post("/book-init-data/{data_id}", response_class=HTMLResponse)
async def update_book_init_data(
    request: Request,
    data_id: int,
    title: str = Form(...),
    content: str = Form(""),
    book_title: str = Form(""),
    db: Session = Depends(get_db),
):
    data = db.query(BookInitData).filter(BookInitData.id == data_id).first()
    if not data:
        raise HTTPException(status_code=404, detail="初始化数据不存在")
    data.title = title
    data.content = content
    data.book_title = book_title
    data.updated_at = get_china_now()
    db.commit()
    return RedirectResponse(url="/materials?tab=init", status_code=303)


@router.post("/book-init-data/{data_id}/delete", response_class=HTMLResponse)
async def delete_book_init_data(data_id: int, db: Session = Depends(get_db)):
    data = db.query(BookInitData).filter(BookInitData.id == data_id).first()
    if not data:
        raise HTTPException(status_code=404, detail="初始化数据不存在")
    db.delete(data)
    db.commit()
    return RedirectResponse(url="/materials?tab=init", status_code=303)


@router.get("/book-init-data/{data_id}/edit", response_class=HTMLResponse)
async def edit_book_init_data_modal(request: Request, data_id: int, db: Session = Depends(get_db)):
    """返回编辑初始化数据的模态框"""
    data = db.query(BookInitData).filter(BookInitData.id == data_id).first()
    if not data:
        raise HTTPException(status_code=404, detail="初始化数据不存在")

    from fastapi.templating import Jinja2Templates

    templates = get_templates()
    return templates.TemplateResponse(
        "partials/edit_modal.html",
        {"request": request, "item": data, "item_type": "init", "action_url": f"/materials/book-init-data/{data_id}"},
    )
