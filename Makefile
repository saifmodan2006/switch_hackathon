.PHONY: setup migrate test web api agents build
setup:
	sh scripts/linux/setup.sh
migrate:
	PYTHONPATH=services/api:services .venv/bin/alembic upgrade head
test:
	.venv/bin/python -m pytest -q
web:
	cd apps/web && npm run dev
api:
	PYTHONPATH=services/api:services .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
agents:
	PYTHONPATH=services/api:services .venv/bin/python -m agents.runtime.engine
build:
	cd apps/web && npm run build
