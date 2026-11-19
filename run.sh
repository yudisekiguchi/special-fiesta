#!/usr/bin/env bash
# Cria o ambiente na primeira vez e abre o servidor em http://127.0.0.1:8000
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
echo "Abra http://127.0.0.1:8000 no navegador (Ctrl+C para parar)"
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
