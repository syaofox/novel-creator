# DeepSeek Novel Studio - Agent Guide

## Project Overview

FastAPI + Pydantic 长篇小说创作平台，使用 DeepSeek API v4，**纯文件存储**(JSON)。

## Architecture

### Data Flow
```
User → HTMX → FastAPI Routes → NovelService → AI Agents → DeepSeek API
                                      ↕
                              FileRepository
                                      ↕
                          JSON Files (data/ + books/)
```

### Storage Layout
```
data/
  ids.json                      # Auto-increment counters
  global_config.json            # Global settings
  materials/
    plot_summaries/{id}.json
    character_cards/{id}.json
    writing_styles/{id}.json
    material_notes/{id}.json
    book_init_data/{id}.json
books/{book_id}/
  meta.json                     # Book metadata
  chapters/{num}.json           # Chapter data
```

### Key Directories
- `app/services/agents/` - AI agent implementations
- `app/repositories/file_repository.py` - File-based storage (replaces SQLAlchemy)
- `app/routes/` - FastAPI route handlers
- `app/utils/` - Prompts, helpers, config
- `app/static/css/styles.css` - Custom CSS (no Tailwind/DaisyUI)
- `app/static/js/htmx.min.js` - HTMX for interactivity
- `app/templates/` - Jinja2 templates using HTMX + custom CSS
- `tests/` - pytest test suite
- **Note**: `app/schemas/` was removed (dead code — all models live in `file_repository.py`)

## Frontend Stack
- **HTMX**: All interactivity (form submits, partial refreshes, modal dialogs)
- **Custom CSS**: Clean, modern design without framework dependencies
- **No JavaScript framework**: Server-rendered HTML via Jinja2

## Test Structure

### Shared Fixtures (`tests/conftest.py`)
- `repo` — `FileRepository` with temp directory
- `sample_book` — Default book with config, memory_summary, style
- `mock_ai_service` — Mocked `AiService` with `global_config = {}`
- `service` — `NovelService(repo, mock_ai_service)`
- `client` — FastAPI `TestClient` with all dependencies overridden

## Cache Optimization (DeepSeek V4)

### Chapter Writer (`chapter_writer_agent.py`)
- **System prompt**: jailbreak + role + **stable sections** (人物卡, 世界观, 风格规范)
- **User prompt**: dynamic sections (主线进度, 伏笔清单, 其他信息) + chapter content

### Summary Agent (`summary_agent.py`)
- **System prompt**: fixed role + format instructions
- **User prompt**: old_summary + new_chapter

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage (target: >85%)
uv run pytest tests/ --cov=app -v

# Lint
uv run ruff check app/ tests/
```
