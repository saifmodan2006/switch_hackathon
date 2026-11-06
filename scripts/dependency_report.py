import importlib.metadata as md
import json
from pathlib import Path

lines=['# Dependency versions and license metadata','',
       'Generated from installed Python distributions and the resolved npm lockfile. This is a metadata inventory, not a legal opinion. Review upstream license files before redistribution.','',
       '## Web dependencies','', '| Package | Version | Declared license |','|---|---|---|']
package=json.loads(Path('apps/web/package.json').read_text())
lock=json.loads(Path('apps/web/package-lock.json').read_text())
for name,version in sorted({**package['dependencies'],**package['devDependencies']}.items()):
    entry=lock['packages']['node_modules/'+name]
    lines.append(f'| {name} | {version} | {entry.get("license","See upstream package")} |')
lines+=['','## Python dependencies','','| Package | Version | Declared license |','|---|---|---|']
for dist in sorted(md.distributions(),key=lambda d:d.metadata['Name'].lower()):
    name=dist.metadata['Name']
    if name.lower()=='pip':continue
    license=dist.metadata.get('License-Expression') or dist.metadata.get('License') or 'See upstream package'
    if '\n' in license or len(license)>100:
        classifiers=[c.split(' :: ')[-1] for c in dist.metadata.get_all('Classifier',[]) if c.startswith('License ::')]
        license=', '.join(classifiers) or 'See upstream license file'
    lines.append(f'| {name} | {dist.version} | {license.replace("|","/")} |')
lines+=['','## Separately deployed services and optional models','',
        '- Switch: official upstream distribution; review the exact installed release license and terms: https://github.com/sandbox-quantum/switch/blob/main/LICENSE . No Switch server code is redistributed in this repository.',
        '- PostgreSQL: PostgreSQL License. pgvector: PostgreSQL License.',
        '- Redis 7.4: review the selected release’s RSALv2/SSPLv1 licensing; do not assume later Redis licensing applies to this pinned image.',
        '- MinIO: GNU AGPLv3; review redistribution, modification and network-use obligations for your deployment.',
        '- Mailpit: MIT. Ollama: MIT. Container base images include additional third-party components.',
        '- Qwen3 and embedding models: review the exact downloaded model repository’s license and acceptable use terms; model weights are not bundled or automatically downloaded.',
        '- Mattermost is a separate supported bridge deployment with its own edition-specific terms.',
        '', 'Exact container image startup, image availability and live compatibility have not been verified because the Docker engine is unavailable. Use a dependency scanner/SBOM tool before release.']
Path('docs/DEPENDENCIES.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Wrote dependency version and license metadata inventory.')
