# AGENTS.md - DeepSeek Novel Studio 开发指南

## 项目概述

基于 FastAPI + SQLAlchemy 的长篇小说创作平台，使用 DeepSeek API 进行 AI 辅助写作。

## 技术栈

- **后端**: FastAPI, SQLAlchemy, Pydantic
- **数据库**: SQLite
- **AI**: DeepSeek API (OpenAI 兼容)
- **前端**: htmx + Tailwind CSS + DaisyUI
- **模板**: Jinja2
- **测试**: pytest, pytest-asyncio, httpx
- **代码质量**: ruff, prettier

## 构建与运行

```bash
# 安装依赖(开发)
uv sync --all-extras

# 安装前端依赖
npm install

# 开发服务器 (自动构建 CSS 并启动)
./run.sh

# 或手动运行
npm run build:css
uv run uvicorn app.main:app --reload

# 数据库迁移
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Lint 与格式化

```bash
# Python 代码检查
uv run ruff check .
uv run ruff check . --fix
uv run ruff format .

# HTML/Jinja2 模板 (注意: prettier 对 Jinja2 支持有限，可能报错)
# 建议将 app/templates 加入 .prettierignore
npx prettier --check app/templates/**/*.html
npx prettier --write app/templates/**/*.html

# 完整检查
uv run ruff check . && uv run ruff format . --check
```

## 测试

```bash
# 运行所有测试
uv run pytest

# 带覆盖率
uv run pytest --cov=app --cov-report=html

# 运行单个测试文件
uv run pytest tests/test_routes.py

# 运行单个测试函数 (推荐方式)
uv run pytest tests/test_routes.py::test_home

# 详细输出 + 失败时停止
uv run pytest -v -x

# 运行指定标记
uv run pytest -m "asyncio"
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

## 前端开发规范 (htmx 优先)

### 原则

- **优先使用 htmx**，避免原生 JS 或 jQuery
- 流式响应等 htmx 不支持的场景可使用 fetch + EventSource
- 表单提交优先使用 htmx 的 `hx-post`

### htmx 请求处理

后端检测 htmx 请求并返回 partial 模板：

```python
from fastapi.responses import HTMLResponse

@router.get("/items")
async def get_items(request: Request):
    is_htmx = request.headers.get("HX-Request") == "true"

    if is_htmx:
        return templates.TemplateResponse("partials/item_list.html", {...})

    return templates.TemplateResponse("items.html", {...})
```

### 创建 htmx 兼容的页面

1. **主页面** (`page.html`): 包含完整 HTML 结构
2. **Partial 模板** (`partials/page_tab.html`): 仅包含内容部分，供 htmx 请求使用

后端路由根据 `HX-Request` header 返回不同模板。

### 表单字段命名

确保前端表单字段名与后端 `Form()` 参数名一致：

```python
# 后端
@router.post("/books/")
async def create_book(
    title: str = Form(...),
    plot_summary: str = Form(""),  # 不是 basic_idea
    ...
):
```

```html
<!-- 前端 -->
<input name="plot_summary" ... />
```

### 页面间数据传递

使用 `sessionStorage` 在页面间传递数据（如预览页需要的表单数据）：

```javascript
// 页面1: 保存数据
sessionStorage.setItem("initStreamUrl", streamUrl);
sessionStorage.setItem("initFormData", JSON.stringify(formData));

// 页面2: 读取数据
const streamUrl = sessionStorage.getItem("initStreamUrl");
const formData = JSON.parse(sessionStorage.getItem("initFormData"));
```

### 避免的问题

1. **prettier 对 Jinja2 支持有限**：将 `app/templates` 加入 `.prettierignore`
2. **模板语法错误**：`{% if %}` 和 `{% endif %}` 必须正确配对，不要在模板中使用复杂的条件嵌套
3. **表单必填字段**：确保 `Form(...)` 必填字段与前端 `required` 属性一致

## Git 提交规范

使用 conventional commits 格式: `type: description`

```bash
git commit -m "feat: 添加新书籍创建功能"
git commit -m "fix: 修复章节保存问题"
git commit -m "chore: 更新 ruff 配置"
```

类型: `feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `test`
