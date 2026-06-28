from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.dependencies import RepoDep
from app.repositories.file_repository import GlobalConfig
from app.utils.helpers import get_templates
from app.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_MAX_TOKENS,
    DEFAULT_STREAM,
    DEFAULT_JAILBREAK_PREFIX,
    DEFAULT_SYSTEM_TEMPLATE,
    AGENT_NAMES,
)

book_settings_router = APIRouter(prefix="/books/{book_id}/settings", tags=["book_settings"])


@book_settings_router.get("/", response_class=HTMLResponse)
async def settings_form(request: Request, book_id: int, repo: RepoDep):
    book = repo.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="书籍不存在")
    templates = get_templates()
    return templates.TemplateResponse(request, "settings.html", {"book": book})


@book_settings_router.post("/", response_class=HTMLResponse)
async def save_settings(request: Request, book_id: int, repo: RepoDep):
    form = await request.form()
    book = repo.get_book(book_id)
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
    repo.update_book(book)
    return RedirectResponse(url=f"/books/{book_id}", status_code=303)


global_settings_router = APIRouter(prefix="/settings", tags=["global_settings"])


@global_settings_router.get("/global", response_class=HTMLResponse)
async def global_settings_form(request: Request, repo: RepoDep):
    config = repo.get_global_config()
    if not config.id:
        config = GlobalConfig()
        repo.save_global_config(config)
    templates = get_templates()
    return templates.TemplateResponse(request, "global_settings.html", {"config": config})


@global_settings_router.post("/global", response_class=HTMLResponse)
async def save_global_settings(request: Request, repo: RepoDep):
    form = await request.form()
    config = repo.get_global_config()
    config.deepseek_api_key = form.get("deepseek_api_key", config.deepseek_api_key or "")
    config.deepseek_base_url = form.get("deepseek_base_url", config.deepseek_base_url or "https://api.deepseek.com")
    agent_models: dict[str, str] = {}
    for agent_name in AGENT_NAMES:
        value = form.get(f"agent_model_{agent_name}")
        if value:
            agent_models[agent_name] = value
    config.agent_models = agent_models
    config.temperature = float(form.get("temperature", config.temperature if config.temperature is not None else DEFAULT_TEMPERATURE))
    config.top_p = float(form.get("top_p", config.top_p if config.top_p is not None else DEFAULT_TOP_P))
    config.max_tokens = int(form.get("max_tokens", config.max_tokens if config.max_tokens is not None else DEFAULT_MAX_TOKENS))
    config.stream = form.get("stream") == "on"
    config.jailbreak_prefix = form.get("jailbreak_prefix", config.jailbreak_prefix or DEFAULT_JAILBREAK_PREFIX)
    config.system_template = form.get("system_template", config.system_template or DEFAULT_SYSTEM_TEMPLATE)
    repo.save_global_config(config)
    return RedirectResponse(url="/", status_code=303)
