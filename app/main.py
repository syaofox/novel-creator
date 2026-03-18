import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.database import engine, get_db
from app import models
from app.routes import books, chapters, ai
from app.routes import materials
from app.routes.settings import book_settings_router, global_settings_router

BASE_DIR = Path(__file__).resolve().parent

# 加载环境变量
load_dotenv()

# 创建数据库表（实际生产应使用 Alembic）
models.Base.metadata.create_all(bind=engine)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    logger.info("应用启动")
    yield
    # 关闭时执行
    logger.info("应用关闭")


app = FastAPI(title="DeepSeek Novel Studio", lifespan=lifespan)

# 挂载静态文件
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# 注册路由
app.include_router(books.router)
app.include_router(chapters.router)
app.include_router(ai.router)
app.include_router(materials.router)
app.include_router(book_settings_router)  # 新增
app.include_router(global_settings_router)  # 新增

# 模板
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, status: str | None = None, db: Session = Depends(get_db)):
    from app.models import Book

    if status == "已完结":
        books = db.query(Book).filter(Book.status == "已完结").order_by(Book.updated_at.desc()).all()
    else:
        books = db.query(Book).filter(Book.status == "进行中").order_by(Book.updated_at.desc()).all()

    is_htmx = request.headers.get("HX-Request") == "true"

    current_status = status or "进行中"

    if is_htmx:
        return templates.TemplateResponse(
            request, "partials/tabs_with_list.html", {"books": books, "status": current_status}
        )

    return templates.TemplateResponse(request, "index.html", {"books": books, "status": current_status})


# 异常处理等可以添加
