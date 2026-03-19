# AGENTS.md - DeepSeek Novel Studio

## 项目概述

FastAPI + SQLAlchemy 长篇小说创作平台，使用 DeepSeek API 进行 AI 辅助写作。

## 技术栈

- **后端**: FastAPI, SQLAlchemy, Pydantic
- **数据库**: SQLite
- **AI**: DeepSeek API (OpenAI 兼容)
- **前端**: htmx + Tailwind CSS + DaisyUI
- **测试**: pytest, pytest-asyncio, httpx
- **工具**: ruff (lint/format), pyright (type check)

## 构建与运行

```bash
# 安装依赖
uv sync --all-extras
npm install

# 开发服务器
./run.sh
# 或手动: npm run build:css && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

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
uv run pytest                                    # 所有测试
uv run pytest tests/test_routes.py::test_home    # 单个测试函数
uv run pytest -v -x                              # 详细输出 + 失败停止
uv run pytest --cov=app --cov-report=html        # 覆盖率
```

## 代码风格

### 通用规则

- Python 3.13+, 行长度 120, 双引号, 4 空格缩进
- 使用 ruff 进行 lint 和格式化 (见 pyproject.toml 配置)

### 导入规范

按顺序分组（标准库 -> 第三方库 -> 本地模块），用空行分隔

```python
import logging
from contextlib import asynccontextmanager
from typing import Any
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.services.ai_service import AiService
```

### 类型注解

- 使用 `str | None` 而非 `Optional[str]`
- 使用 `dict[str, Any]` 而非 `Dict[str, Any]`
- 使用 `list[str]` 而非 `List[str]`
- 使用 `Annotated[T, Depends(...)]` 定义依赖注入类型

### 命名规范

- 函数/变量: snake_case (`get_book`, `create_chapter`)
- 类: PascalCase (`BookService`, `BaseAgent`)
- 常量: UPPER_SNAKE_CASE (`MAX_TOKENS`, `DEFAULT_STYLE`)

### 异步代码

- 使用 `AsyncOpenAI` 而非 `OpenAI`
- Agent 支持三种模式: `run()`, `run_stream()`, `run_json()`

### 错误处理

- 自定义异常继承 `NovelCreatorException` (见 `app/core/exceptions.py`)
- 使用具体异常类型，避免裸 `except:`

### Pydantic/SQLAlchemy

- 使用 `Column` 显式定义列
- 使用 `Field` 定义带验证的字段
- Pydantic 模型使用 `class Config: from_attributes = True`

### AI API 调用规范

- **所有 AI API 调用都必须使用 `jailbreak_prefix`**
- 使用 `_get_config_value()` 获取配置（优先级：书籍配置 > 全局配置 > 默认值）

## 目录结构

```
app/
├── main.py              # FastAPI 入口
├── config.py            # 配置 (pydantic-settings)
├── constants.py         # 常量定义
├── database.py          # SQLAlchemy 连接
├── models.py            # SQLAlchemy 模型
├── schemas.py           # Pydantic schemas (legacy)
├── core/
│   ├── dependencies.py  # FastAPI 依赖注入 (AiServiceDep, NovelServiceDep, DbSession)
│   └── exceptions.py    # 自定义异常
├── repositories/
│   └── novel_repository.py  # 数据访问层
├── services/
│   ├── ai_service.py        # AI 服务
│   ├── base_ai_service.py   # 基础 AI 服务 (call_llm, call_llm_stream)
│   ├── novel_service.py     # 小说业务逻辑
│   ├── file_service.py      # 文件操作
│   └── agents/
│       ├── base_agent.py        # Agent 基类 + AgentFactory
│       ├── plot_agent.py        # 剧情 Agent
│       ├── init_book_agent.py   # 书籍初始化 Agent
│       ├── chapter_writer_agent.py  # 章节写作 Agent
│       └── summary_agent.py     # 摘要 Agent
├── schemas/             # Pydantic 模型 (按功能分文件)
├── routes/              # FastAPI 路由
├── utils/
│   ├── config_helper.py # 配置辅助
│   ├── helpers.py
│   ├── json_helper.py
│   └── prompts.py
├── templates/           # Jinja2 模板
│   └── partials/        # htmx 局部模板
└── static/              # 静态文件 (css/, js/)
tests/                   # pytest 测试
alembic/                 # 数据库迁移
```

## 分层架构规范

### Repository 层

```python
from app.repositories.novel_repository import NovelRepository
repo = NovelRepository(db)
book = repo.get_book_by_id(book_id)
```

### Service 层

```python
from app.core.dependencies import NovelServiceDep
@router.get("/books/{book_id}")
async def get_book(book_id: int, service: NovelServiceDep):
    return service.get_book(book_id)
```

### Agent 层

```python
from app.services.agents import AgentFactory, BaseAgent
from app.services.base_ai_service import BaseAiService

class MyAgent(BaseAgent):
    system_prompt = "你的角色描述..."
    def build_prompt(self, **kwargs) -> str:
        return f"任务描述: {kwargs.get('input')}"

AgentFactory.register("my_agent", MyAgent)
agent = AgentFactory.create("my_agent", ai_service)
result = await agent.run(input="任务输入")
```

### 依赖注入类型

```python
from app.core.dependencies import DbSession, AiServiceDep, NovelServiceDep
async def my_endpoint(db: DbSession, service: NovelServiceDep):
    ...
```

### 异常处理

```python
from app.core.exceptions import NovelCreatorException, BookNotFoundError, ChapterNotFoundError, AIServiceError
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

### HTMX 最佳实践

- 使用 `hx-confirm` 替代内联 JavaScript 确认框
- 利用 `htmx-indicator` 类自动处理加载状态
- 使用 `hx-push-url` 更新浏览器 URL 而不刷新页面

## Git 提交

```bash
git commit -m "feat: 添加新功能"
git commit -m "fix: 修复问题"
git commit -m "refactor: 重构代码"
```

类型: `feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `test`
