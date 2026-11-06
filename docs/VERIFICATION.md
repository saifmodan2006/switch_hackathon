# Executed verification

**Current live results:** see [November 7 live verification](LIVE_VERIFICATION.md). The historical unavailable-service statements below describe the earlier build environment and are superseded for the core sandbox workflow. Latest deterministic suite: 22 passed; updated production web build passed. Real Gemini, official Switch, Mattermost, PostgreSQL, Redis, MinIO, Mailpit and exact-version human approval were exercised successfully.

Build environment: Windows, PowerShell, Node **24.21.0**, Python **3.12.10**, npm-resolved Next **16.4.5**, React **19.3.1**, TypeScript **7.0.2**, Tailwind **4.3.5**, FastAPI **0.162.0**, SQLAlchemy **2.1.8**, Pydantic **2.14.3**, Alembic **1.20.1**, HTTPX **0.28.1**, websockets **17.4**, Playwright **1.65.0**. Complete installed package versions and license metadata are in `docs/DEPENDENCIES.md`; Python and npm dependencies are pinned.

## Executed and passed

| Command / check | Observed result |
|---|---|
| `py -3.12 -m venv .venv` and pip install | Dependencies installed in project virtual environment |
| `.venv\Scripts\python -m pip check` | No broken requirements |
| `npm install`, then pinned package/lockfile resolution | Installation successful; npm audit reported 0 vulnerabilities at build time |
| `alembic revision --autogenerate` | Initial explicit schema migration generated |
| `alembic upgrade head` | SQLite upgraded through `c80c1be47388` and `d1c3_pgvector` |
| `.venv\Scripts\python -m pytest -q` | **22 passed**, final deterministic suite |
| `.venv\Scripts\python -m pytest tests/live -q` | **2 skipped**, explicit missing live-service configuration |
| `npm run typecheck --prefix apps/web` | Passed |
| `npm run build --prefix apps/web` | Production compile/typecheck/route generation passed |
| `npm run test:e2e --prefix apps/web` | **1 comprehensive Chromium test passed** (30.8 seconds on the final expanded journey) |
| `docker compose config --quiet` | Compose configuration validates |
| `python -m compileall -q services` | Python source compilation passed |
| `python scripts/export_openapi.py` | **63 API paths** exported to shared contracts |
| Uvicorn startup + `/api/v1/health` | API starts and health returns HTTP 200 |
| Next dev startup + browser test server | Frontend starts; real browser navigates the application |
| Final `python scripts/doctor.py` | Database connected at `d1c3_pgvector`; frontend **200**, backend **200**, Switch unconfigured, model ConnectError |

The deterministic suite verifies auth/CSRF, CRM CRUD/duplicates, tenant isolation, idempotency conflicts, valid/invalid state transitions, exact human approval and replay/expiry, viewer authorization denial, knowledge extraction/search/deletion, safe CSV, tasks/calendar/ICS, genuine TCP SMTP transport to a controlled test sink, registration key preservation, operation discovery/permission errors, cursor dedup/pongs/takeover/gap, genuine TCP WebSocket transport to a controlled protocol fixture, full customer-proposal-approval-send-follow-up persistence, forged sender rejection, disconnected Switch fail-closed behavior and stale handoff timeout.

The full deterministic pipeline test checks six addressed handoffs and seven actual adapter model invocations using deterministic test outputs. It verifies no send before approval, one send after approval, a persisted follow-up and analytics updates. **The model, Switch network and email provider in that test are controlled test doubles, not evidence of live Switch or real inference.** Separate transport tests exercise actual WebSocket and SMTP sockets against controlled local protocol servers.

## Browser evidence

The comprehensive Playwright test uses isolated `.data/e2e.db` and ports 3011/8011, separate from the user’s local application database. It exercises:

1. Real account/workspace registration through the UI.
2. Explicit synthetic seed action and actual SQL-derived counts.
3. Customer creation, reload and persistence.
4. Task-board navigation.
5. Command request creation and durable workflow detail.
6. A clearly labeled isolated synthetic approval fixture, inspection and authenticated approval decision.
7. Visible unconfigured Switch connection error.
8. Mobile menu/navigation and no horizontal document overflow at 390px.
9. All remaining major workspace sections and dark-theme switching.
10. No uncaught browser page errors.

Actual screenshots: `docs/screenshots/overview-desktop.png` and `docs/screenshots/overview-mobile.png`. They show the real app with a labeled synthetic QA workspace; they are not mockups or generated AI images. Toasts are allowed to dismiss before capture. The mobile hero was adjusted after visual inspection to preserve its action and text.

## Problems found and resolved

- SQLAlchemy async required its `greenlet` extra; installed and pinned it.
- Transaction rollback expired ORM objects in two runtime error paths; capture stable identifiers before rollback and explicitly reload.
- Browser test startup initially raced browser installation; installed the required Chromium and headless shell.
- A simultaneous local/test Next server initially shared its development build directory; isolated E2E output as `.next-e2e`.
- Browser assertions had an ambiguous customer locator and expected a toast not emitted by Command Center; corrected selectors and asserted durable timeline state instead.
- Initial small/muted type and mobile hero clipping were improved after inspecting actual screenshots.
- Registration addressing failure could discard a one-time key; registration now commits credentials before the follow-up remote operation.

No unexplained test failure remains in the final executed deterministic/browser results.

The local web, API and singleton agent runtime were left running for review. No real agent connectivity is implied by the runtime process being active. Create an account at http://localhost:3000; there is no shared default password.

## Unverified and incomplete

- Docker CLI exists, but `docker info` cannot reach `dockerDesktopLinuxEngine`; no running Linux engine was available. Container image pulls/builds/startup, PostgreSQL-specific pgvector migration/index behavior, Redis/ARQ and MinIO/Mailpit service behavior remain **unverified**.
- `SWITCH_SERVER_URL` and registration credentials were absent. There is no installed Switch server version, real agent registration, real room-template import, actual Mattermost conversation or live two-agent exchange to report.
- The local model endpoint is unreachable (`ConnectError`). No actual Ollama/hosted inference or real generated proposal has been verified. Test fixtures are explicitly labeled.
- SMTP is not configured outside Compose. The real TCP test sink verifies the adapter transport; actual Mailpit capture and external delivery are unverified.
- Google credentials/account consent were absent. OAuth, refresh and free/busy code are implemented against documented official endpoints but unverified live. Sending external calendar invitations is not implemented.
- A public deployment, submission repository URL and video were not created. No public URLs are invented.
- Secondary missing functionality and security limits are listed in `docs/ACCEPTANCE.md` and `docs/security/SECURITY.md`. These are engineering scope limits, not all environmental blockers.

## Run the real integration checks

Only after provisioning dedicated test identities/room (not production conversations):

```powershell
$env:RUN_LIVE_SWITCH='1'
$env:LIVE_SWITCH_URL='https://your-actual-switch-bridge'
$env:LIVE_SWITCH_ROOM_ID='<dedicated-test-room-id>'
$env:LIVE_SWITCH_AGENT_ID_1='<dedicated-test-agent-id-1>'
$env:LIVE_SWITCH_AGENT_ID_2='<dedicated-test-agent-id-2>'
$env:LIVE_SWITCH_AGENT_NAME_1='<dedicated-test-agent-name-1>'
$env:LIVE_SWITCH_AGENT_NAME_2='<dedicated-test-agent-name-2>'
# Supply LIVE_SWITCH_AGENT_KEY_1 and LIVE_SWITCH_AGENT_KEY_2 securely in this shell.
# Do not paste them into source, screenshots or a shared terminal transcript.
.venv\Scripts\python -m pytest tests/live -m live -q
```

`RUN_LIVE_MODEL=1` separately enables actual structured inference using the configured model and synthetic input. The full real business demonstration remains the manual, auditable sequence in `docs/hackathon/DEMO_SCRIPT.md`.
