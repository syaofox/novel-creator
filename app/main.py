import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.core.dependencies import RepoDep
from app.routes import books, chapters, ai
from app.routes import materials
from app.routes.settings import book_settings_router, global_settings_router
from app.utils.helpers import get_templates

BASE_DIR = Path(__file__).resolve().parent

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("应用启动")
    yield
    logger.info("应用关闭")


app = FastAPI(title="DeepSeek Novel Studio", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(books.router)
app.include_router(chapters.router)
app.include_router(ai.router)
app.include_router(materials.router)
app.include_router(book_settings_router)
app.include_router(global_settings_router)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, status: str | None = None, repo: RepoDep = None):
    if status == "已完结":
        books = repo.get_books(status="已完结")
    else:
        books = repo.get_books(status="进行中")

    is_htmx = request.headers.get("HX-Request") == "true"

    current_status = status or "进行中"

    if is_htmx:
        return get_templates().TemplateResponse(
            request, "partials/tabs_with_list.html", {"books": books, "status": current_status}
        )

    return get_templates().TemplateResponse(request, "index.html", {"books": books, "status": current_status})
