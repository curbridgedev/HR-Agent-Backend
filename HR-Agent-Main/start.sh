#!/bin/bash
# Start script for Railway deployment
uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT

