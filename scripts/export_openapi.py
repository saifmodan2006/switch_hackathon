import json
from pathlib import Path
from app.main import app
target=Path('packages/shared-contracts/openapi.json')
target.write_text(json.dumps(app.openapi(),indent=2),encoding='utf-8')
print(f'Exported {len(app.openapi()["paths"])} API paths to {target}')
