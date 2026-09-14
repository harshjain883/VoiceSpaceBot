#!/bin/bash
set -e

# Start FastAPI Server in background
echo "Starting FastAPI Web Server on port 8080..."
python -m uvicorn server:app --host 0.0.0.0 --port 8080 &

# Sleep 2 seconds for server initialization
sleep 2

# Start Pyrogram Bot in foreground
echo "Starting Pyrogram Voice Space Bot..."
python bot.py
