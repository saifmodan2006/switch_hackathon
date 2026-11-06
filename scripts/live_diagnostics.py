"""Read only known local service logs, redacting deployment secrets before output."""
import subprocess
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from dotenv import dotenv_values

def redact(text):
    for path in [Path('.env'), Path('.data/live/switch/.env'), Path('.data/live/access.env')]:
        if path.exists():
            for name, value in dotenv_values(path).items():
                if value and len(value)>7 and any(word in name.upper() for word in ('KEY','PASSWORD','TOKEN','SECRET')):
                    text=text.replace(value,'[redacted]')
    return text

if __name__=='__main__':
    for container in sys.argv[1:]:
        if not container.startswith('switchops-'):
            raise ValueError('Only project containers may be inspected')
        result=subprocess.run(['docker','logs','--tail','65',container],capture_output=True,text=True,encoding='utf-8',errors='replace')
        print(container+'\n'+redact(result.stdout+result.stderr))
