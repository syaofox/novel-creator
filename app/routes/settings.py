from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Book, GlobalConfig
from app.utils.config_helper import get_global_config_dict
from fastapi.templating import Jinja2Templates
from app.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_MAX_TOKENS,
    DEFAULT_STREAM,
    DEFAULT_JAILBREAK_PREFIX,
    DEFAULT_SYSTEM_TEMPLATE,
    TEMPLATE_DIR,
    DEFAULT_MODEL,
)


# 书籍设置路由
book_settings_router = APIRouter(prefix="/books/{book_id}/settings", tags=["book_settings"])


@book_settings_router.get("/", response_class=HTMLResponse)
async def settings_form(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    return templates.TemplateResponse(request, "settings.html", {"book": book})


@book_settings_router.post("/", response_class=HTMLResponse)
async def save_settings(request: Request, book_id: int, db: Session = Depends(get_db)):
    form = await request.form()
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    config = book.config
    config["temperature"] = float(form.get("temperature", config.get("temperature", DEFAULT_TEMPERATURE)))
    config["top_p"] = float(form.get("top_p", config.get("top_p", DEFAULT_TOP_P)))
    config["max_tokens"] = int(form.get("max_tokens", config.get("max_tokens", DEFAULT_MAX_TOKENS)))
    config["stream"] = form.get("stream") == "on"
    config["jailbreak_prefix"] = form.get("jailbreak_prefix", config.get("jailbreak_prefix", ""))
    config["system_template"] = form.get("system_template", config.get("system_template", ""))
    book.config = config
    db.commit()
    return RedirectResponse(url=f"/books/{book_id}", status_code=303)


# 全局设置路由
global_settings_router = APIRouter(prefix="/settings", tags=["global_settings"])


@global_settings_router.get("/global", response_class=HTMLResponse)
async def global_settings_form(request: Request, db: Session = Depends(get_db)):
    config = db.query(GlobalConfig).filter(GlobalConfig.id == 1).first()
    if not config:
        config = GlobalConfig(
            id=1,
            temperature=str(DEFAULT_TEMPERATURE),
            top_p=str(DEFAULT_TOP_P),
            max_tokens=DEFAULT_MAX_TOKENS,
            stream=1 if DEFAULT_STREAM else 0,
            jailbreak_prefix=DEFAULT_JAILBREAK_PREFIX,
            system_template=DEFAULT_SYSTEM_TEMPLATE,
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    return templates.TemplateResponse(request, "global_settings.html", {"config": config})


@global_settings_router.post("/global", response_class=HTMLResponse)
async def save_global_settings(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    config = db.query(GlobalConfig).filter(GlobalConfig.id == 1).first()
    if not config:
        config = GlobalConfig(id=1)
        db.add(config)
    config.deepseek_api_key = form.get("deepseek_api_key", config.deepseek_api_key or "")
    config.deepseek_base_url = form.get("deepseek_base_url", config.deepseek_base_url or "https://api.deepseek.com/v1")
    config.default_model = form.get("default_model", config.default_model or DEFAULT_MODEL)
    config.temperature = float(form.get("temperature", config.temperature or DEFAULT_TEMPERATURE))
    config.top_p = float(form.get("top_p", config.top_p or DEFAULT_TOP_P))
    config.max_tokens = int(form.get("max_tokens", config.max_tokens or DEFAULT_MAX_TOKENS))
    config.stream = form.get("stream") == "on"
    config.jailbreak_prefix = form.get("jailbreak_prefix", config.jailbreak_prefix or DEFAULT_JAILBREAK_PREFIX)
    config.system_template = form.get("system_template", config.system_template or DEFAULT_SYSTEM_TEMPLATE)
    db.commit()
    return RedirectResponse(url="/", status_code=303)
