import logging

from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PlotSummary, CharacterCard, WritingStyle, get_china_now
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

    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    return templates.TemplateResponse(
        request,
        "materials.html",
        {
            "plot_summaries": plot_summaries,
            "character_cards": character_cards,
            "writing_styles": writing_styles,
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
