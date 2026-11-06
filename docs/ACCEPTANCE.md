# Acceptance matrix

**Live update, November 7:** [live verification](LIVE_VERIFICATION.md) supersedes the historical “unverified live” entries below for the core workflow. PostgreSQL migrated to `e20_switch_bigint`; official Switch/Mattermost, all six distinct agents, real Gemini research/drafting/review, explicit owner approval, exact-content Mailpit capture, follow-up scheduling, completion analytics and a fail-closed outage probe passed. Desktop Console connection remains unverified; no production delivery is claimed. Broader feature gaps below remain applicable.

This matrix distinguishes delivered behavior, deterministic verification, missing scope and external verification gaps. It is deliberately not a claim that the entire original specification has passed.

| Final criterion | Status | Evidence / remaining work |
|---|---|---|
| Frontend starts | Verified locally | Next dev served; production build passed; real Playwright runs |
| Backend starts | Verified locally | Uvicorn startup and HTTP health 200 |
| Database migrates | Verified on SQLite | Both Alembic revisions applied; PostgreSQL/pgvector migration still needs a real service |
| Authentication | Verified | Registration, login, cookie/CSRF, logout, session rotation/revocation tests |
| Customer management persists | Verified | API CRUD/duplicates/tenant tests and browser create/reload |
| Business requests persist | Verified | API idempotency and browser request creation/detail |
| Real Switch server connected | Unverified | No server, registration key or room credentials available |
| Two distinct agents exchange real Switch messages | Unverified live | Six-identity protocol fixture passes, but is not a live deployment |
| Human interacts in genuine room | Implemented, unverified live | Verified identity mapping and incoming request handler; actual Mattermost needed |
| Handoffs update durable workflow | Verified with protocol fixtures | HTTP room posts → persisted event receipts → specialist execution |
| Research/proposal uses real model | Implemented, unverified live | Real Ollama/OpenAI-compatible adapter; no model endpoint available |
| Proposal available for review | Verified with explicit synthetic fixture | Version persistence, review UI, download/edit code; real inference still required |
| Unauthorized actions blocked | Verified for tested cases | Role/CSRF/tenant/forged participant tests; not an independent security certification |
| Human approval enforced | Verified | Conditional exact decision, expiry, payload hash, immutable versions, replay checks |
| Approved send reaches provider | Verified against controlled SMTP test sink | Real TCP smtplib exercised; actual Mailpit/production recipient remains unverified |
| Follow-up persists | Verified in deterministic full workflow | Task and internal event created after accepted send and Switch handoff |
| Full activity inspectable | Verified locally | Workflow event history, approval fields and audit UI |
| Analytics update from actual records | Verified | SQL metrics/assertions; no random activity |
| All tests executed without unexplained failures | See VERIFICATION | Final executed counts/results recorded there; live suite cannot pass without services |
| Reproducible Windows setup | Implemented and locally exercised in parts | PowerShell setup/start, pinned dependencies, environment bootstrap and Alembic; clean-machine Docker reproduction unverified |

## Broader feature scope

| Area | Delivered | Incomplete / limitation |
|---|---|---|
| UI | All 16 sections; responsive nav; light/dark; forms/dialogs/toasts; actual-data views | No organization-specific visual customization or granular notification preferences |
| CRM | CRUD/archive, search/stage, duplicate email checks, CSV, notes/tags/owner/opt-out, workflow/history view | Advanced multi-field sorting, contact timestamps/communication preferences beyond opt-out and generic interaction API |
| Inbox | Manual requests; classification + suggested draft API/UI with real configured inference; low confidence triage | Connected-email ingestion, threading synchronization, Gmail OAuth and production inbound webhooks |
| Tasks | List/board, status, owner, priority, due date, comments, scoped dependency validation API, reminders worker | Drag/drop, attachment uploads, dependency graph/cycle management and rich assignment picker |
| Calendar | Internal event CRUD, overlap checks, timezone-aware timestamps, ICS, Google OAuth/refresh/free-busy API | Calendar month/week grid and approval-controlled external invitation creation; external availability UI integration |
| Knowledge | Four text-bearing formats, scoped chunks, citations, keyword fallback, optional embedding/pgvector code, cleanup | Optional ML packages/model and PostgreSQL indexing not executed here; no OCR; extractor needs stronger process isolation |
| Documents | Versioned proposals, immutable approved body, Markdown/PDF download, human revision | Visual version diff and all requested reusable professional document templates |
| Approvals | Proposal/external email exact version/action; role/expiry/hash/replay; human changes/rejection | General calendar/sensitive CRM/export/destructive/custom approval types; chat approvals deliberately unsupported |
| Models | Ollama/OpenAI-compatible, model override, probe/timeout/privacy, usage and errors | Provider pricing/cost configuration, full context-window governance and model performance tuning |
| Rooms | Genuine mapped IDs/links, official-format five-room group YAML, exact sender/room checks | Live template import, participant/membership synchronization UI and automatic cross-room workflow routing |
| Team/admin | Roles, token invitations, membership switching, identity map and org settings | Email verification, MFA/SSO/password recovery, invitation email, owner transfer, retention purge |
| Reliability | State machine, dedup/idempotency, optimistic workflow concurrency, leadership lock, budgets, reconnect backoff, approval expiration, handoff timeout, failed-event inspection API and explicit blocked failures | Distributed outbox reconciliation after crashes, dead-letter recovery UI, automated stale handoff recovery and multi-runtime horizontal scale |
| Analytics | Actual counts/tokens/timestamps/date-filtered workflow chart, baseline estimate | Universal customer/agent/date filters in UI, price-derived costs, communication response-rate analysis and full success-rate reporting |
| Infrastructure | Compose/Dockerfiles/health checks/volumes, CI, private object adapter, JSON request logs | Docker build/start and PostgreSQL/Redis/MinIO/Mailpit/Ollama service compatibility unverified; full OTel/exporter stack absent |
| Schema | Explicit core tables; shared typed/discriminated resource storage for smaller domains | Not all original conceptual entities have their own dedicated normalized tables |

Do not conceal these limits in the hackathon submission. The remaining live validation is a concrete integration dependency, while missing secondary features are engineering work, not credential blockers.
