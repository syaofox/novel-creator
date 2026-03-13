import logging

from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PlotSummary, CharacterCard, WritingStyle, MaterialNote, BookInitData, get_china_now
from app.constants import DEFAULT_STYLE, TEMPLATE_DIR

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

    templates = Jinja2Templates(directory=TEMPLATE_DIR)
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
    request: Request, title: str = Form(...), content: str = Form(""), db: Session = Depends(get_db)
):
    new_plot = PlotSummary(title=title, content=content)
    db.add(new_plot)
    db.commit()
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


@router.post("/character-cards", response_class=HTMLResponse)
async def create_character_card(
    request: Request, title: str = Form(...), content: str = Form(""), db: Session = Depends(get_db)
):
    new_card = CharacterCard(title=title, content=content)
    db.add(new_card)
    db.commit()
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
    db: Session = Depends(get_db),
):
    if is_default == 1:
        db.query(WritingStyle).update({"is_default": 0})
    new_style = WritingStyle(title=title, content=content, is_default=is_default)
    db.add(new_style)
    db.commit()
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
    request: Request, title: str = Form(...), content: str = Form(""), db: Session = Depends(get_db)
):
    new_note = MaterialNote(title=title, content=content)
    db.add(new_note)
    db.commit()
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

    templates = Jinja2Templates(directory=TEMPLATE_DIR)

    if is_htmx:
        return templates.TemplateResponse(
            request,
            "partials/materials_tab.html",
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

    templates = Jinja2Templates(directory=TEMPLATE_DIR)
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

    templates = Jinja2Templates(directory=TEMPLATE_DIR)
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

    templates = Jinja2Templates(directory=TEMPLATE_DIR)
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

    templates = Jinja2Templates(directory=TEMPLATE_DIR)
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

    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    return templates.TemplateResponse(
        "partials/edit_modal.html",
        {"request": request, "item": data, "item_type": "init", "action_url": f"/materials/book-init-data/{data_id}"},
    )
