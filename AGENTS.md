# DeepSeek Novel Studio - Agent Guide

## Project Overview

FastAPI + SQLAlchemy 长篇小说创作平台，使用 DeepSeek API v4，通过智能摘要机制确保长上下文内不丢失人设与伏笔。

## Architecture

### Data Flow
```
User → HTMX → FastAPI Routes → NovelService → AI Agents → DeepSeek API
                                      ↕
                              NovelRepository
                                      ↕
                              SQLite Database
```

### Key Directories
- `app/services/agents/` - AI agent implementations
- `app/routes/` - FastAPI route handlers
- `app/models.py` - SQLAlchemy models
- `app/utils/` - Prompts, helpers, config
- `tests/` - pytest test suite

## Cache Optimization (DeepSeek V4)

The prompt system is structured for maximum cache hit ratio:

### Chapter Writer (`chapter_writer_agent.py`)
- **System prompt**: jailbreak + role + **stable sections** (人物卡, 世界观, 风格规范)
- **User prompt**: dynamic sections (主线进度, 伏笔清单, 其他信息) + chapter-specific content
- Rationale: Stable sections rarely change → system prompt stays same across chapters → high cache hit on ~2000 tokens

### Summary Agent (`summary_agent.py`)
- **System prompt**: fixed role + format instructions (always same → cached)
- **User prompt**: old_summary + new_chapter (must change → cache miss)

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=app -v

# Type check
uv run pyright app/

# Lint
uv run ruff check app/ tests/
```
