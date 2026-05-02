#!/bin/bash
set -e

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

mkdir -p dist/ScoreReportTool

./.venv/bin/pyinstaller \
    --noconfirm \
    --windowed \
    --name "ScoreReportTool" \
    --add-data "app:app" \
    main.py

mv dist/ScoreReportTool dist/ScoreReportTool_linux 2>/dev/null || true
mv dist/main dist/ScoreReportTool_linux 2>/dev/null || true