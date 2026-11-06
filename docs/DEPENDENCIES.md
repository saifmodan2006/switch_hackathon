# Dependency versions and license metadata

Generated from installed Python distributions and the resolved npm lockfile. This is a metadata inventory, not a legal opinion. Review upstream license files before redistribution.

## Web dependencies

| Package | Version | Declared license |
|---|---|---|
| @hookform/resolvers | 7.0.3 | MIT |
| @phosphor-icons/react | 2.1.10 | MIT |
| @playwright/test | 1.65.0 | Apache-2.0 |
| @radix-ui/react-dialog | 1.3.1 | MIT |
| @radix-ui/react-slot | 1.5.0 | MIT |
| @tailwindcss/postcss | 4.3.5 | MIT |
| @tanstack/react-query | 5.106.1 | MIT |
| @types/node | 26.6.6 | MIT |
| @types/react | 19.3.0 | MIT |
| @types/react-dom | 19.3.0 | MIT |
| class-variance-authority | 0.7.1 | Apache-2.0 |
| clsx | 2.1.1 | MIT |
| geist | 1.9.2 | SIL OPEN FONT LICENSE |
| lucide-react | 1.70.0 | ISC |
| motion | 14.10.1 | MIT |
| next | 16.4.5 | MIT |
| react | 19.3.1 | MIT |
| react-dom | 19.3.1 | MIT |
| react-hook-form | 7.91.0 | MIT |
| recharts | 3.10.1 | MIT |
| sonner | 2.0.8 | MIT |
| tailwind-merge | 3.7.0 | MIT |
| tailwindcss | 4.3.5 | MIT |
| typescript | 7.0.2 | Apache-2.0 |
| zod | 4.6.7 | MIT |
| zustand | 5.1.0 | MIT |

## Python dependencies

| Package | Version | Declared license |
|---|---|---|
| aiosqlite | 0.22.1 | See upstream package |
| alembic | 1.20.1 | MIT |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.16.0 | MIT |
| argon2-cffi | 25.1.0 | MIT |
| argon2-cffi-bindings | 26.1.0 | MIT |
| arq | 0.28.0 | MIT |
| asyncpg | 0.32.0 | Apache-2.0 |
| boto3 | 1.43.125 | Apache-2.0 |
| botocore | 1.43.125 | Apache-2.0 |
| certifi | 2026.10.23 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| colorama | 0.4.6 | See upstream package |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| dnspython | 2.9.2 | ISC |
| email-validator | 2.3.0 | Unlicense |
| fastapi | 0.162.0 | MIT |
| filelock | 4.2.9 | MIT |
| greenlet | 3.5.6 | MIT AND PSF-2.0 |
| h11 | 0.16.0 | MIT |
| hiredis | 3.5.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| jmespath | 1.1.0 | MIT |
| lxml | 6.1.3 | BSD-3-Clause |
| Mako | 1.4.3 | MIT |
| MarkupSafe | 3.0.4 | BSD-3-Clause |
| opentelemetry-api | 1.45.2 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pillow | 13.0.0 | MIT-CMU |
| pluggy | 1.7.0 | MIT |
| pycparser | 3.12 | BSD-3-Clause |
| pydantic | 2.14.3 | MIT |
| pydantic-settings | 2.16.2 | MIT |
| pydantic_core | 2.50.4 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| PyJWT | 2.15.1 | MIT |
| pypdf | 7.0.0 | BSD-3-Clause |
| pytest | 9.2.0 | MIT |
| pytest-asyncio | 1.4.1.post1 | Apache-2.0 |
| python-dateutil | 2.9.0.post0 | Dual License |
| python-docx | 1.2.0 | MIT |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| python-multipart | 0.0.33 | Apache-2.0 |
| redis | 5.3.1 | MIT |
| reportlab | 5.1.0 | BSD license (see license.txt for details), Copyright (c) 2000-2025, ReportLab Inc. |
| respx | 0.23.1 | BSD-3-Clause |
| s3transfer | 0.19.3 | Apache License 2.0 |
| six | 1.17.0 | MIT |
| SQLAlchemy | 2.1.8 | MIT |
| starlette | 1.10.0 | BSD-3-Clause |
| typing-inspection | 0.4.5 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| urllib3 | 2.8.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| websockets | 17.4 | BSD-3-Clause |

## Separately deployed services and optional models

- Switch: official upstream distribution; review the exact installed release license and terms: https://github.com/sandbox-quantum/switch/blob/main/LICENSE . No Switch server code is redistributed in this repository.
- PostgreSQL: PostgreSQL License. pgvector: PostgreSQL License.
- Redis 7.4: review the selected release’s RSALv2/SSPLv1 licensing; do not assume later Redis licensing applies to this pinned image.
- MinIO: GNU AGPLv3; review redistribution, modification and network-use obligations for your deployment.
- Mailpit: MIT. Ollama: MIT. Container base images include additional third-party components.
- Qwen3 and embedding models: review the exact downloaded model repository’s license and acceptable use terms; model weights are not bundled or automatically downloaded.
- Mattermost is a separate supported bridge deployment with its own edition-specific terms.

Exact container image startup, image availability and live compatibility have not been verified because the Docker engine is unavailable. Use a dependency scanner/SBOM tool before release.
