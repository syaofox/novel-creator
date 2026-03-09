import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from app.database import engine
from app import models
from app.routes import books, chapters, ai
from app.routes.settings import book_settings_router, global_settings_router  # 修改点

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
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 注册路由
app.include_router(books.router)
app.include_router(chapters.router)
app.include_router(ai.router)
app.include_router(book_settings_router)  # 新增
app.include_router(global_settings_router)  # 新增

# 模板
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# 异常处理等可以添加
