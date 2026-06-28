# DeepSeek Novel Studio - Agent Guide

## Project Overview

FastAPI + Pydantic 长篇小说创作平台，使用 DeepSeek API v4，**纯文件存储**(JSON)替代 SQLite。

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
- `tests/` - pytest test suite

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

# Run with coverage
uv run pytest tests/ --cov=app -v

# Lint
uv run ruff check app/ tests/
```
