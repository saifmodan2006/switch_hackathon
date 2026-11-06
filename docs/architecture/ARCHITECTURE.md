# Architecture and failure boundaries

## Business state

FastAPI uses SQLAlchemy async sessions and Alembic. Organizations, users, memberships, revocable sessions, CRM, workflows, immutable events, agent identities/receipts, generated versions, approvals, deliveries, knowledge/chunks, integrations, usage, audit and idempotency each have explicit tables. Smaller tenant resources (tasks, internal calendar, inbox, interactions, notifications, invitations and comments) share a `records` table with a discriminator and validated JSON metadata. This is an intentional compact model, not an implementation of every table listed in the original specification. The acceptance matrix records the difference.

Every user query uses the authenticated organization, and cross-entity customer/workflow references are ownership-checked. The browser cannot choose the tenant by sending a username or arbitrary header. Membership changes revoke active sessions for the affected organization. PostgreSQL is the Compose target; SQLite is a single-host development fallback with foreign-key enforcement.

## Collaboration path

1. Dashboard creates a durable workflow and CREATED event with an idempotency record when supplied. A verified human’s genuine Switch request can also create a workflow when the CRM customer match is unambiguous.
2. One runtime leader owns each database (PostgreSQL advisory lock, SQLite file lock). The coordinator requires a live room heartbeat, posts the request to Switch, triages with real inference, and posts an explicit addressed handoff.
3. Switch delivers a WebSocket frame to the next identity. The socket immediately services pings; it only persists the event receipt, leaving slow model work out of the heartbeat loop.
4. The durable consumer checks addressed=true, membership in the actual covered room set, exact opaque sender participant, current expected specialist and handoff sequence. A room message alone does not grant arbitrary tool access.
5. Each specialist retrieves only its allowed context. Its validated model result is persisted, cited, posted into the actual Switch room, then passed to the next specialist by a genuine room message.
6. Communications saves a new immutable proposal version. Quality checks claims. An expiring exact-payload approval is created and a real review link is posted in the workflow room.
7. An owner/admin/manager uses the authenticated dashboard to decide. Approval uses a conditional PENDING update and records actor/reason/hash. Text in a chat never authorizes an external action.
8. Communications atomically persists a unique send claim, sends via SMTP, records acceptance/uncertainty and hands off through Switch to scheduling. Internal follow-up task/event persist; scheduling messages the coordinator to finalize.

The topical rooms are supplemental collaboration contexts. The executable flagship pipeline stays in operations-hub with all six identities, making every handoff inspectable in one thread. Automatic cross-room routing is not claimed.

## Reliability

Workflow transitions follow CREATED → TRIAGING → RESEARCHING → DRAFTING → REVIEWING → AWAITING_APPROVAL → APPROVED → EXECUTING → COMPLETED. Exceptional states are BLOCKED, FAILED, CANCELLED, REJECTED and NEEDS_INFORMATION. Revision returns to DRAFTING. A human retry starts a fresh collaboration attempt while preserving history and budgets.

- Connection IDs survive restart; cursor/generation persist. The server’s connection_state is authoritative.
- Duplicate receipts use `(agent_id, sequence)` uniqueness and processed status; stale or forged handoff sequences do not invoke models.
- Switch network reconnection backs off to 60 seconds. Permission/auth/fencing refusal and permanent eviction stop the agent rather than causing takeover loops.
- Gaps fail closed and require room-history reconciliation and human intervention. They do not quietly fast-forward a workflow.
- Each workflow has configured model-call and handoff budgets. There is no infinite agent loop.
- Failed receipt details and workflow errors persist; no fabricated replacement inference exists.
- The send claim commits before network I/O. Any ambiguous SMTP outcome requires manual inspection. Exactly-once remote delivery cannot be guaranteed by SMTP; automatic resend is deliberately disabled.
- PostgreSQL advisory leadership currently serializes business model execution in one runtime. Stale handoffs block after the configured timeout and expired approvals are invalidated. Horizontal scaling, automatic handoff recovery/outbox reconciliation and high-volume task queues need further engineering.
- A crash between a remote room post and business commit may leave a visible uncorrelated message; workflow IDs and handoff expectations limit side effects. Full distributed exactly-once publishing is not claimed.

## Live UI and analytics

The browser uses TanStack Query and an authenticated SSE invalidation endpoint based on committed audit records. It does not synthesize agent speech. Connectivity polls every 15 seconds, workflow details every 10 seconds while visible. Query caches are invalidated on mutations and real persisted audit changes.

Counts use tenant SQL aggregates. Average completion/approval time derives from stored timestamps. Estimated saved time is `max(0, completed_count × manual_baseline_minutes − sum(elapsed_completion_minutes))`. Cost is unknown until a price policy exists; the UI displays no fabricated dollar estimate. Some summary counters are workspace-wide while the execution chart/date aggregates are filtered; this is documented, not a claim of universal filter propagation.

## Storage and retrieval

Uploads are restricted to text-bearing PDF/DOCX/TXT/Markdown with byte, PDF-page and DOCX expansion limits. Extracted text is chunked with overlap. Default keyword matching exposes a meaningful lexical overlap score. Optional local embeddings use the configured Sentence Transformers model. PostgreSQL stores 384-dimensional vectors in a pgvector HNSW index; SQLite uses JSON and exact cosine scanning. Existing keyword-only documents must be reuploaded after enabling embeddings. Citations return source document ID, title and chunk location.

MinIO stores uploads/proposals privately when configured. Every download is authorized through the API. Local development retains contents in SQL. Knowledge deletion removes the stored object and chunk rows; generated versions are retained for approval evidence. PDF download uses ReportLab and escaped text rather than executing arbitrary HTML.
