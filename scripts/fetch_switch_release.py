"""Fetch a pinned official Switch Compose OCI artifact and verify its SHA-256."""
import hashlib
import json
from pathlib import Path
import httpx

VERSION = '0.31.0'
REPOSITORY = 'sandbox-quantum/standalone-compose'
out = Path('.data/live/switch')
out.mkdir(parents=True, exist_ok=True)
with httpx.Client(timeout=60, follow_redirects=True) as http:
    token = http.get('https://ghcr.io/token', params={'scope': f'repository:{REPOSITORY}:pull'}).json()['token']
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.oci.image.manifest.v1+json'}
    response = http.get(f'https://ghcr.io/v2/{REPOSITORY}/manifests/{VERSION}', headers=headers)
    response.raise_for_status()
    manifest = response.json()
    layer = manifest['layers'][0]
    response = http.get(f'https://ghcr.io/v2/{REPOSITORY}/blobs/{layer["digest"]}', headers=headers)
    response.raise_for_status()
    if 'sha256:' + hashlib.sha256(response.content).hexdigest() != layer['digest']:
        raise RuntimeError('Official Compose artifact digest mismatch')
    (out/'compose.yaml').write_bytes(response.content)
    (out/'release.json').write_text(json.dumps({'version': VERSION, 'digest': layer['digest'], 'source': manifest['annotations']['org.opencontainers.image.source']}, indent=2))
    print(f'Official Switch {VERSION} Compose artifact downloaded and digest verified.')
