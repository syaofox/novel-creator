from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Book, GlobalConfig
from fastapi.templating import Jinja2Templates

# 书籍设置路由
book_settings_router = APIRouter(prefix="/books/{book_id}/settings", tags=["book_settings"])

@book_settings_router.get("/", response_class=HTMLResponse)
async def settings_form(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("settings.html", {"request": request, "book": book})

@book_settings_router.post("/", response_class=HTMLResponse)
async def save_settings(request: Request, book_id: int, db: Session = Depends(get_db)):
    form = await request.form()
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    config = book.config
    config["temperature"] = float(form.get("temperature", config["temperature"]))
    config["top_p"] = float(form.get("top_p", config["top_p"]))
    config["max_tokens"] = int(form.get("max_tokens", config["max_tokens"]))
    config["jailbreak_prefix"] = form.get("jailbreak_prefix", config["jailbreak_prefix"])
    config["system_template"] = form.get("system_template", config["system_template"])
    book.config = config
    db.commit()
    return RedirectResponse(url=f"/books/{book_id}", status_code=303)

# 全局设置路由
global_settings_router = APIRouter(prefix="/settings", tags=["global_settings"])

@global_settings_router.get("/global", response_class=HTMLResponse)
async def global_settings_form(request: Request, db: Session = Depends(get_db)):
    config = db.query(GlobalConfig).filter(GlobalConfig.id == 1).first()
    if not config:
        config = GlobalConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("global_settings.html", {"request": request, "config": config})

@global_settings_router.post("/global", response_class=HTMLResponse)
async def save_global_settings(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    config = db.query(GlobalConfig).filter(GlobalConfig.id == 1).first()
    if not config:
        config = GlobalConfig(id=1)
        db.add(config)
    config.deepseek_api_key = form.get("deepseek_api_key", config.deepseek_api_key)
    config.deepseek_base_url = form.get("deepseek_base_url", config.deepseek_base_url)
    config.default_model = form.get("default_model", config.default_model)
    db.commit()
    return RedirectResponse(url="/", status_code=303)