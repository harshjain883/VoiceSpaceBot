#!/bin/bash
set -e

echo "Starting FastAPI Web Server on port 8080..."
uvicorn server:app --host 0.0.0.0 --port 8080 &

echo "Starting Pyrogram Voice Space Bot..."
python bot.py
