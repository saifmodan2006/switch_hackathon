# Shared contracts

The source of truth is FastAPI OpenAPI at `/openapi.json`. Export it with
`python scripts/export_openapi.py`. Frontend DTOs live in `apps/web/lib/api.ts`.
Do not store agent keys in frontend contracts.
