"""Run a reviewed project maintenance script inside the API, secrets on stdin only."""
import json
import subprocess
import sys
from pathlib import Path
from dotenv import dotenv_values

script=Path(sys.argv[1]).resolve()
if script.parent != (Path.cwd()/'scripts').resolve():
    raise ValueError('Only project scripts can run through this helper')
values={**dotenv_values('.data/live/switch/.env'),**dotenv_values('.data/live/access.env')}
prelude='LIVE_CONFIG = '+repr(values)+'\n'
result=subprocess.run(['docker','exec','-i','switchops-api-1','python','-u','-'],input=prelude+script.read_text(encoding='utf-8'),
    text=True,encoding='utf-8')
raise SystemExit(result.returncode)
