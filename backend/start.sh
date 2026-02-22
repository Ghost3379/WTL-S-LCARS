#!/bin/bash
# Startup script for WTl-S-LCARS backend

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Navidrome configuration
export NAVIDROME_URL="${NAVIDROME_URL:-http://localhost:4533}"
export NAVIDROME_USERNAME="${NAVIDROME_USERNAME:-your_username}"
export NAVIDROME_PASSWORD="${NAVIDROME_PASSWORD:-your_password}"

# Run the Flask app
python3 app.py
