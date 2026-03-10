# AGENTS.md - DeepSeek Novel Studio 开发指南

## 项目概述

基于 FastAPI + SQLAlchemy 的长篇小说创作平台，使用 DeepSeek API 进行 AI 辅助写作。

## 技术栈

- **后端**: FastAPI, SQLAlchemy, Pydantic
- **数据库**: SQLite
- **AI**: DeepSeek API (OpenAI 兼容)
- **模板**: Jinja2
- **测试**: pytest, pytest-asyncio, httpx
- **代码质量**: ruff, prettier

## 构建与运行

```bash
# 安装依赖
uv sync

# 激活虚拟环境
source .venv/bin/activate

# 开发服务器
uvicorn app.main:app --reload

# 或
fastapi dev app/main.py

# 数据库迁移
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Lint 与格式化

```bash
# Python 代码检查
ruff check .
ruff check . --fix
ruff format .

# HTML/Jinja2 模板
npx prettier --check app/templates/**/*.html
npx prettier --write app/templates/**/*.html

# 完整检查
ruff check . && ruff format . --check && npx prettier --check app/templates/**/*.html
```

## 测试

```bash
# 运行所有测试
pytest

# 带覆盖率
pytest --cov=app --cov-report=html

# 运行单个测试文件
pytest tests/test_routes.py

# 运行单个测试函数 (推荐方式)
pytest tests/test_routes.py::test_home

# 详细输出 + 失败时停止
pytest -v -x

# 运行指定标记
pytest -m "asyncio"
```

## 代码风格指南

### 通用规则

- **Python 版本**: 3.13+
- **行长度**: 120 字符
- **引号**: 双引号 `"`
- **缩进**: 4 空格

### 导入规范 (按顺序排列，空行分隔)

```python
# 标准库
import json
import re
from typing import Any

# 第三方库
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# 本地模块
from app.models import Book
from app.schemas import BookCreate
```

- 使用绝对导入，避免相对导入 `from ..models import`

### 类型注解

```python
# 正确
def func(x: str, y: int | None = None) -> dict[str, Any]:
    ...

# 错误
def func(x: str, y: Optional[int] = None) -> Dict[str, Any]:
    ...
```

- 使用 `str | None` 而非 `Optional[str]`
- 使用 `dict`, `list` 而非 `Dict`, `List`

### 命名规范

- 函数/变量: snake_case (`get_book`, `book_id`)
- 类: PascalCase (`BookService`, `ChapterModel`)
- 常量: UPPER_SNAKE_CASE (`MAX_TOKENS`)
- 文件: snake_case (`book_service.py`)

### 异步代码

```python
# 正确：处理 None 返回值
response = await client.chat.completions.create(...)
return response.choices[0].message.content or ""
```

- 使用 `AsyncOpenAI` 而非 `OpenAI`
- 避免在 async 函数中使用同步阻塞调用

### 错误处理

```python
# 正确
try:
    data = json.loads(content)
except json.JSONDecodeError:
    return fallback_data

# 错误：避免 bare except
```

- 使用具体异常类型，避免 `except:`

### Pydantic 模型

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

- 使用 `Field` 定义带验证的字段

### SQLAlchemy 模型

- 使用 `Column` 显式定义列
- 默认值使用 `default=`，避免 `server_default`
- 使用 `JSON` 类型存储复杂配置

### FastAPI 路由

```python
router = APIRouter(prefix="/books", tags=["books"])

@router.get("/{book_id}")
async def get_book(book_id: int, db: Session = Depends(get_db)):
    ...
```

## 目录结构

```
app/
├── main.py           # FastAPI 应用入口
├── config.py         # 配置管理
├── database.py       # 数据库连接
├── models.py         # SQLAlchemy 模型
├── schemas.py        # Pydantic 模型
├── routes/           # API 路由
├── services/         # 业务逻辑
├── utils/            # 工具函数
├── templates/        # Jinja2 模板
└── static/           # 静态文件
alembic/              # 数据库迁移
tests/                # 测试文件
data/                 # 数据库文件
```

## 常见任务

### 添加新路由

1. 在 `app/routes/` 创建路由文件
2. 在 `app/main.py` 引入并注册 Router
3. 定义 Pydantic schema（如果需要）
4. 编写测试

### 添加数据库模型

1. 在 `app/models.py` 添加 SQLAlchemy 模型
2. 创建迁移: `alembic revision --autogenerate -m "add xxx"`
3. 执行迁移: `alembic upgrade head`

### 添加 AI 功能

1. 在 `app/services/` 创建服务类
2. 使用 `AsyncOpenAI` 调用 API
3. 正确处理 `None` 返回值
4. 添加超时和错误处理

## Git 提交规范

使用 conventional commits 格式: `type: description`

```bash
git commit -m "feat: 添加新书籍创建功能"
git commit -m "fix: 修复章节保存问题"
git commit -m "chore: 更新 ruff 配置"
```

类型: `feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `test`
