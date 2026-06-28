# DeepSeek Novel Studio Workflow

## Development

```bash
# Install dependencies
uv sync --all-extras

# Build CSS
npm run build:css

# Run dev server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage (target: >85%)
uv run pytest tests/ --cov=app -v

# Lint
uv run ruff check app/ tests/
```

## Code Rules

- All async AI calls go through `AiService` class
- New agents extend `BaseAgent` and register via `AgentFactory.register()`
- All prompts live in `app/utils/prompts.py`
- Stable sections (人物卡, 世界观, 风格规范) go in system prompt for cache optimization
- Dynamic sections (主线进度, 伏笔清单) go in user prompt
- Storage uses JSON files via `FileRepository` (NOT SQLAlchemy/SQLite)
- Every Python change needs pytest tests
- Run `ruff check` before committing

## Common Tasks

### Adding a new AI agent
1. Create `app/services/agents/my_agent.py` extending `BaseAgent`
2. Register via `AgentFactory.register("my_agent", MyAgent)`
3. Add to `app/services/agents/__init__.py`
4. Write tests in `tests/test_agents.py`

### Adding a new route
1. Create `app/routes/my_routes.py`
2. Include router in `app/main.py`
3. Use `repo: RepoDep` for storage access
4. Write integration test in `tests/test_routes_integration.py`
