#!/bin/bash
set -e

echo "Building CSS..."
npm run build:css

echo "Starting dev server..."
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
