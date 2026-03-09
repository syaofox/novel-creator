# AGENTS.md - DeepSeek Novel Studio 开发指南

## 项目概述

基于 FastAPI + SQLAlchemy 的长篇小说创作平台，使用 DeepSeek API 进行 AI 辅助写作。

## 技术栈

- **后端**: FastAPI, SQLAlchemy, Pydantic
- **数据库**: SQLite (开发) / 可扩展到 PostgreSQL
- **AI**: DeepSeek API (OpenAI 兼容)
- **模板**: Jinja2
- **测试**: pytest, pytest-asyncio, httpx
- **代码质量**: ruff, prettier

---

## 构建与运行

### 环境设置

```bash
# 使用 uv 安装依赖
uv sync

# 激活虚拟环境
source .venv/bin/activate
```

### 开发服务器

```bash
# 方式1: uvicorn 直接运行
uvicorn app.main:app --reload

# 方式2: fastapi-cli
fastapi dev app/main.py
```

### 数据库

```bash
# 创建迁移
alembic revision --autogenerate -m "description"

# 执行迁移
alembic upgrade head
```

---

## Lint 与格式化

### Python 代码

```bash
# 检查代码
ruff check .

# 自动修复
ruff check . --fix

# 格式化代码
ruff format .
```

### HTML/Jinja2 模板

```bash
# 检查模板格式
npx prettier --check app/templates/**/*.html

# 格式化模板
npx prettier --write app/templates/**/*.html
```

### 完整检查

```bash
# 运行所有检查
ruff check . && ruff format . --check && npx prettier --check app/templates/**/*.html
```

---

## 测试

```bash
# 运行所有测试
pytest

# 运行所有测试（带覆盖率）
pytest --cov=app --cov-report=html

# 运行单个测试文件
pytest tests/test_routes.py

# 运行单个测试函数
pytest tests/test_routes.py::test_home

# 运行指定标记的测试
pytest -m "asyncio"

# 查看详细输出
pytest -v

# 失败时立即停止
pytest -x
```

---

## 代码风格指南

### 通用规则

- **Python 版本**: 3.13+
- **行长度**: 120 字符
- **引号**: 双引号 `"`
- **缩进**: 4 空格

### 导入规范

```python
# 标准库
import json
import re
from typing import Any, Optional

# 第三方库
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# 本地模块
from app.models import Book
from app.schemas import BookCreate
from app.utils import prompts
```

- 使用绝对导入，避免相对导入 `from ..models import`
- 按标准库 → 第三方 → 本地顺序排列
- 每组之间空一行

### 类型注解

- 使用 Python 3.13+ 新语法 (`str | None` 替代 `Optional[str]`)
- 使用 `dict` 而非 `Dict`
- 使用 `list` 而非 `List`
- 使用 `collections.abc` 而非 `typing` 中的对应类型

```python
# 正确
def func(x: str, y: int | None = None) -> dict[str, Any]:
    ...

# 错误
def func(x: str, y: Optional[int] = None) -> Dict[str, Any]:
    ...
```

### 命名规范

- **函数/变量**: snake_case (`get_book`, `book_id`)
- **类**: PascalCase (`BookService`, `ChapterModel`)
- **常量**: UPPER_SNAKE_CASE (`MAX_TOKENS`, `DEFAULT_MODEL`)
- **文件**: snake_case (`book_service.py`, `user_routes.py`)

### 异步代码

- 使用 `async/await`，避免在 async 函数中使用同步阻塞调用
- 使用 `AsyncOpenAI` 而非 `OpenAI`
- 正确处理 `None` 返回值

```python
# 正确
response = await client.chat.completions.create(...)
return response.choices[0].message.content or ""

# 错误
response = await client.chat.completions.create(...)
return response.choices[0].message.content  # 可能返回 None
```

### 错误处理

- 使用具体的异常类型，避免 bare `except`
- 捕获异常后提供有意义的处理或日志

```python
# 正确
try:
    data = json.loads(content)
except json.JSONDecodeError:
    return fallback_data

# 错误
try:
    data = json.loads(content)
except:
    return fallback_data
```

### Pydantic 模型

- 使用 `Field` 定义带验证的字段
- 使用 `from_attributes = True` 允许从 ORM 模型创建

```python
class BookCreate(BaseModel):
    title: str
    genre: str

class BookOut(BookCreate):
    id: int
    config: dict[str, Any]

    class Config:
        from_attributes = True
```

### SQLAlchemy 模型

- 使用 `Column` 显式定义列
- 默认值使用 `default=`，不要使用 `server_default`（除非必要）
- 使用 `JSON` 类型存储复杂配置

### FastAPI 路由

- 使用依赖注入获取数据库会话
- 使用 `response_class=HTMLResponse` 返回 HTML
- 路由前缀使用 Router 的 `prefix` 参数

```python
router = APIRouter(prefix="/books", tags=["books"])

@router.get("/{book_id}")
async def get_book(book_id: int, db: Session = Depends(get_db)):
    ...
```

### 模板文件

- 使用 Jinja2 语法
- 遵循 Prettier 默认格式化规则
- HTML 属性使用双引号

### Git 提交

- 使用conventional commits格式: `type: description`
- 类型: `feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `test`

```bash
git commit -m "feat: 添加新书籍创建功能"
git commit -m "fix: 修复章节保存问题"
git commit -m "chore: 更新 ruff 配置"
```

---

## 目录结构

```
.
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI 应用入口
│   ├── config.py         # 配置管理
│   ├── database.py       # 数据库连接
│   ├── models.py         # SQLAlchemy 模型
│   ├── schemas.py        # Pydantic 模型
│   ├── routes/          # API 路由
│   │   ├── books.py
│   │   ├── chapters.py
│   │   ├── ai.py
│   │   └── settings.py
│   ├── services/        # 业务逻辑
│   │   ├── ai_service.py
│   │   └── file_service.py
│   ├── utils/          # 工具函数
│   │   ├── helpers.py
│   │   └── prompts.py
│   ├── templates/      # Jinja2 模板
│   └── static/         # 静态文件
├── alembic/           # 数据库迁移
├── tests/             # 测试文件
├── books/             # 书籍章节文件存储
├── pyproject.toml     # 项目配置
└── .prettierrc       # Prettier 配置
```

---

## 常见任务

### 添加新路由

1. 在 `app/routes/` 创建路由文件
2. 在 `app/main.py` 引入并注册 Router
3. 定义 Pydantic schema（如果需要）
4. 编写测试

### 添加数据库模型

1. 在 `app/models.py` 添加 SQLAlchemy 模型
2. 创建 Alembic 迁移: `alembic revision --autogenerate -m "add xxx"`
3. 执行迁移: `alembic upgrade head`

### 添加 AI 功能

1. 在 `app/services/` 创建服务类
2. 使用 `AsyncOpenAI` 调用 API
3. 正确处理 `None` 返回值
4. 添加适当的超时和错误处理
