#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../.."
python3.12 -m venv .venv
.venv/bin/pip install -r services/api/requirements.txt
.venv/bin/python scripts/init_env.py
PYTHONPATH=services/api:services .venv/bin/alembic upgrade head
npm ci --prefix apps/web
