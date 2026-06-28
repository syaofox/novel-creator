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

## Chapter Writing Flow

### Write / Generate
1. `GET /books/{id}/chapters/write` — shows form with title (optional), core_event, prev_ending
2. `POST /books/{id}/chapters/` — generates content via `ChapterWriterAgent` (stream or direct)
   - Uses injected `service.ai_service` (no manual AiService creation)
   - Accepts `title`, `core_event`, `regenerate` (bool) form params
   - Returns `edit_chapter.html` with content for user review/edit
3. `POST /books/{id}/chapters/save` — saves chapter content
   - Accepts `chapter_number`, `title`, `content`
   - Calls `NovelService.save_chapter()` with optional title
   - Returns OOB chapter list update + save confirmation

### Regenerate
1. `GET /books/{id}/chapters/regenerate?num=X` — shows `write_chapter.html` with pre-filled title + core_event
   - `regenerate=True` query param sets button text to "重新生成" instead of "生成章节"
   - Uses `write_chapter_form` internally (reuses the same UI)
2. Form POSTs to `POST /chapters/` with `regenerate=true` hidden field
3. Generation and save follow the same flow as new chapter

### Add Chapter
1. `GET /books/{id}/chapters/add` — shows form with position select, title, core_event
2. `POST /books/{id}/chapters/add` — inserts chapter at position, renumbers existing ones
3. Response uses `hx-swap="innerHTML"` targeting `#chapter-list` (preserves wrapper div)

### Delete Chapter
1. `DELETE /books/{id}/chapters/{num}` — deletes and renumbers remaining chapters

## Summary Update

### AI Update Summary
1. `POST /books/{id}/ai/stream-summary` — SSE stream of updated summary via `SummaryAgent`
   - After streaming completes: auto-saves summary + extracts optimized title/core_event
   - Auto-save via `POST /books/{id}/ai/save-summary` (handled in JS)
2. `POST /books/{id}/ai/save-summary` — persisted by `NovelService.save_summary_with_chapter_update()`
   - Also updates chapter's title and/or core_event if provided

### Key NovelService Methods
- `save_summary_with_chapter_update(book, summary, chapter_number, title, core_event)` — saves summary and optionally updates chapter metadata

## AI Service Dependency
All routes now use injected `AiService` via `AiServiceDep` / `service.ai_service`:
- `get_ai_service(repo)` creates AiService with proper global_config
- No manual `AiService()` instantiation in route handlers

## Cache Optimization (DeepSeek V4)

### Chapter Writer (`chapter_writer_agent.py`)
- **System prompt**: jailbreak + role + **stable sections** (人物卡, 世界观, 风格规范)
- **User prompt**: dynamic sections (主线进度, 伏笔清单, 其他信息) + chapter content

### Summary Agent (`summary_agent.py`)
- **System prompt**: fixed role + format instructions
- **User prompt**: old_summary + new_chapter

### Optimize Outline (`novel_service.py:optimize_outline()`)
- Not an agent — a direct LLM call from NovelService
- Used in the `添加新章节` form to optimize user's title + core_event
- Sends: style + 人物卡 + 世界观 + 主线进度 + 伏笔清单 + user's draft
- Configurable via `optimize_outline_user_prompt` (global / per-book)

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage (target: >85%)
uv run pytest tests/ --cov=app -v

# Lint
uv run ruff check app/ tests/
```
