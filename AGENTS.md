# AGENTS.md - DeepSeek Novel Studio

## 项目概述

FastAPI + SQLAlchemy 长篇小说创作平台，使用 DeepSeek API 进行 AI 辅助写作。

## 技术栈

- **后端**: FastAPI, SQLAlchemy, Pydantic
- **数据库**: SQLite
- **AI**: DeepSeek API (OpenAI 兼容)
- **前端**: htmx + Tailwind CSS + DaisyUI
- **测试**: pytest, pytest-asyncio, httpx

## 构建与运行

```bash
# 安装依赖
uv sync --all-extras
npm install

# 开发服务器
./run.sh
# 或手动: npm run build:css && uv run uvicorn app.main:app --reload

# 数据库迁移
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Lint 与测试

```bash
# Python 检查/修复/格式化
uv run ruff check .
uv run ruff check . --fix
uv run ruff format .

# 测试
uv run pytest                        # 所有测试
uv run pytest tests/test_routes.py::test_home  # 单个测试函数
uv run pytest -v -x                  # 详细输出 + 失败停止
uv run pytest --cov=app --cov-report=html  # 覆盖率
```

## 代码风格

### 通用规则

- Python 3.13+, 行长度 120, 双引号 ", 4 空格缩进

### 导入规范 (按顺序，空行分隔)

```python
# 标准库
import json
from typing import Any

# 第三方库
from fastapi import APIRouter, Depends

# 本地模块
from app.models import Book
```

- 使用绝对导入，避免 `from ..models import`

### 类型注解

```python
# 正确
def func(x: str, y: int | None = None) -> dict[str, Any]:

# 错误
def func(x: str, y: Optional[int] = None) -> Dict[str, Any]:
```

- 使用 `str | None` 而非 `Optional[str]`
- 使用 `dict`, `list` 而非 `Dict`, `List`

### 命名规范

- 函数/变量: snake_case (`get_book`)
- 类: PascalCase (`BookService`)
- 常量: UPPER_SNAKE_CASE (`MAX_TOKENS`)

### 异步代码

```python
response = await client.chat.completions.create(...)
return response.choices[0].message.content or ""
```

- 使用 `AsyncOpenAI` 而非 `OpenAI`

### 错误处理

- 使用具体异常类型，避免 `except:`

### Pydantic/SQLAlchemy

```python
class BookOut(BookCreate):
    id: int
    class Config:
        from_attributes = True
```

- 使用 `Column` 显式定义列
- 使用 `Field` 定义带验证的字段

## 目录结构

```
app/
├── main.py           # FastAPI 入口
├── config.py         # 配置
├── database.py       # 数据库连接
├── models.py         # SQLAlchemy 模型
├── core/             # 核心模块
│   ├── dependencies.py  # 依赖注入 (get_db, get_ai_service, get_novel_service)
│   └── exceptions.py    # 自定义异常类
├── repositories/     # 数据访问层
│   └── novel_repository.py
├── services/         # 业务逻辑层
│   ├── ai_service.py       # AI 服务 (DeepSeek API)
│   ├── base_ai_service.py # 基础 AI 服务 (LLM 调用封装)
│   ├── novel_service.py    # 小说业务逻辑
│   ├── file_service.py    # 文件操作
│   └── agents/            # Agent 实现
│       ├── base_agent.py  # Agent 基类 + 工厂
│       └── plot_agent.py  # 示例 Agent
├── schemas/         # Pydantic 模型 (拆分后的目录)
│   ├── __init__.py
│   ├── book.py
│   ├── chapter.py
│   ├── materials.py
│   └── settings.py
├── routes/          # API 路由 (只调用 service)
├── templates/       # Jinja2 模板
└── static/         # 静态文件
tests/               # 测试
alembic/            # 迁移
```

## 分层架构规范

### Repository 层

```python
from app.repositories.novel_repository import NovelRepository

repo = NovelRepository(db)
book = repo.get_book_by_id(book_id)
chapters = repo.get_chapters(book_id)
```

### Service 层

```python
from app.core.dependencies import NovelServiceDep

# 路由中使用依赖注入
@router.get("/books/{book_id}")
async def get_book(book_id: int, service: NovelServiceDep):
    book = service.get_book(book_id)
```

### Agent 层 (新增 Agent)

```python
from app.services.agents import AgentFactory
from app.services.base_ai_service import BaseAiService

class MyAgent(BaseAgent):
    system_prompt = "你的角色描述..."

    def build_prompt(self, **kwargs) -> str:
        return f"任务描述: {kwargs.get('input')}"

# 注册 Agent
AgentFactory.register("my_agent", MyAgent)

# 使用 Agent
agent = AgentFactory.create("my_agent", ai_service)
result = await agent.run(input="任务输入")
```

### 依赖注入类型

```python
from app.core.dependencies import DbSession, AiServiceDep, NovelServiceDep

# 在路由中直接使用
async def my_endpoint(db: DbSession, service: NovelServiceDep):
    ...
```

### 异常处理

```python
from app.core.exceptions import (
    NovelCreatorException,
    BookNotFoundError,
    ChapterNotFoundError,
    AIServiceError,
)

# 路由中抛出
if not book:
    raise BookNotFoundError(book_id)
```

## 前端开发 (htmx 优先)

- 优先使用 htmx，避免原生 JS
- 表单提交使用 `hx-post`
- htmx 请求检测: `request.headers.get("HX-Request") == "true"`
- 页面结构: 主页面 + `partials/` 目录下的局部模板

### 避免的问题

- htmx 页面切换会重新执行 script，注意变量重复声明
- 使用 `window.xxx = window.xxx || value` 或 `if (typeof xxx === "undefined")`
- 表单字段名必须与后端 `Form()` 参数名一致

## Git 提交

```bash
git commit -m "feat: 添加新功能"
git commit -m "fix: 修复问题"
```

类型: `feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `test`
