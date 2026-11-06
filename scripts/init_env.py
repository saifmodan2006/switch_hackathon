"""Create local secrets once. Never print or overwrite an existing .env."""
from pathlib import Path
import secrets
from cryptography.fernet import Fernet

root=Path(__file__).resolve().parents[1]
target=root/'.env'
if target.exists():
    print('Existing .env preserved.')
else:
    text=(root/'.env.example').read_text(encoding='utf-8')
    text=text.replace('REPLACE_WITH_RANDOM_SECRET',secrets.token_urlsafe(48))
    text=text.replace('REPLACE_WITH_FERNET_KEY',Fernet.generate_key().decode())
    text=text.replace('REPLACE_WITH_DB_PASSWORD',secrets.token_urlsafe(24))
    text=text.replace('REPLACE_WITH_MINIO_PASSWORD',secrets.token_urlsafe(24))
    target.write_text(text,encoding='utf-8')
    print('Created .env with private local secrets. No credentials were printed.')
(root/'.data').mkdir(exist_ok=True)
