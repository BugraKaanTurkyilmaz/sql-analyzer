#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if [ ! -d ".venv" ]; then
  echo "Sanal ortam oluşturuluyor..."
  python3 -m venv .venv
  .venv/bin/pip install -q flask
fi

echo "Uygulama başlatılıyor → http://127.0.0.1:5001"
open "http://127.0.0.1:5001" 2>/dev/null || true
.venv/bin/python app.py
