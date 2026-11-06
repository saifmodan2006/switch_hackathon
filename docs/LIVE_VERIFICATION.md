# Live business workflow verification

Executed November 7, 2026, Asia/Kolkata, against the existing project. All customer data was fictional. This verifies the local sandbox workflow, not production readiness.

| Step | Result and evidence |
|---|---|
| Infrastructure | PostgreSQL 17/pgvector, Redis 7.4, private MinIO, Mailpit, API, ARQ worker and agent runtime ran in Docker. PostgreSQL migrated to `e20_switch_bigint`. |
| Official Switch | Released official Compose artifact and core/Gateway/setup images, version 0.31.0; Mattermost 11.9.0. No replacement server or private handoff bus. |
| Six identities | Coordinator, customer intelligence, research, communications, quality and scheduling registered with separate encrypted keys and verified opaque participant IDs. |
| Incoming request | Actual Mattermost post `asrjtjbzd788bj5qjapew1hs6r`, marker `LIVE-ACME-6717e3c7`. Posted by the authorized verification runner using the demo human-role account; not claimed as manual typing. |
| Research | Real Gemini `gemini-3.5-flash-lite` structured inference, saved fictional CRM facts and uploaded private MinIO knowledge source. Research was scoped internal retrieval, not public-web research. |
| Collaboration | Workflow `107e32a8-0f88-45ed-b3f2-11a2a32efe0b`: 10 real model calls, 8 genuine addressed Switch handoffs, all six agents executed. Usage: 28,041 input and 6,183 output tokens. |
| Proposal/review | Version 1 retained. Automated integration review rejected unsupported provisioning claims and requested changes. Version 2 removed them and passed a fresh real model review. This also demonstrates that AI quality review alone is insufficient. |
| Human approval | Project owner explicitly answered “Approve proposal v2 for Mailpit” in the conversation. Submitted through the authenticated application as delegated demo operator, approval `7f342201-113f-4b60-8679-527d1ffd504f`. |
| Sandbox send | Exactly one Mailpit capture, ID `EXgku2BenvpW66xxGSincw`, recipient `acme@example.test`. Captured text equals approved v2 after SMTP CRLF normalization. SHA256 `4bea5107b6ba2ca750428d5615934fefe343749644254fffb67a50c53200ee73`. No real customer delivery asserted. |
| Follow-up | One persisted task and one 15-minute internal calendar event, November 9 at 18:34 UTC (November 10 at 00:04 IST). No external invitations. |
| Completion | Original workflow reached `COMPLETED`; dashboard analytics contain actual usage and completion, zero pending approvals. |
| Switch outage | Stopped the official Switch core. Separate request `89ff30fb-792a-4c91-9025-83ddc13caa33` became `BLOCKED`, zero model calls, zero handoffs, six disconnected agents. Completed records remained readable and Mailpit remained at one message. |

## Integration failures corrected

- Native Gemini API support uses `generateContent`, API-key header, structured schema and provider token usage. Gemini 2.5 Flash returned a new-user availability error; 3.8 Flash returned high-demand errors. The successful available model is configurable 3.5 Flash Lite. Transient status errors retry finitely; failures never become fabricated output.
- Real Switch cursors/generations exceed PostgreSQL int32: migrated to bigint. Shared backend image prevents migrations and workers using stale code.
- Registration now preserves one-time credentials even when subsequent policy configuration fails. The official Gateway owner API configured supported addressing policies.
- Participant mappings came from actual signed room events, including the Mattermost human identity. Room context is read through discovered Switch operations.
- Refreshed heartbeat state before handoffs, retained revision context across explicit retries, added bounded quality revision routing and startup reconnection grace.
- Official MinIO binary/image endpoints were unavailable. The Dockerfile builds unchanged official release source at pinned commit `f19c534b9f457773dcd043d977433e1a71525c3b`, with its AGPL license.
- A deliberately closed Switch connection remains terminal until operator recovery. `resume_live_connections.py` uses the supported authenticated mapping endpoint and retains IDs, rooms, keys, generation and cursors. Gap/takeover conditions still require investigation; do not blindly resume them.

## Access and repeatable checks

Validation: all 24 Python tests passed; updated web production build passed; the comprehensive Chromium journey passed in 54.6 seconds, including persisted records and 390px navigation. The initial 45-second overall browser limit was insufficient during concurrent Docker compilation; the suite now allows 150 seconds. New Gemini protocol tests separately cover schema, key handling, transient retry, thought-part filtering, usage and external-data consent. Read-only browser captures against the live production Docker app verified the overview, workflow, agents, approvals and 390px layout without browser exceptions or mobile horizontal overflow; see `docs/screenshots/live-*.png`.

Open the application at http://localhost:3000, Mattermost at http://localhost:8065, Gateway at http://localhost:3080 and Mailpit at http://localhost:8025. Private generated local credentials are in `.data/live/ACCESS.md` (ignored by Git).

```powershell
.venv\Scripts\python scripts/live_status.py
.venv\Scripts\python scripts/verify_live_outcome.py
docker compose ps
```

Private detailed evidence is saved under `.data/live/`: workflow snapshot, exact proposal files, human authorization evidence, outcome evidence and outage evidence. These include fictional business records and are intentionally not committed wholesale.

Deployment helpers: `fetch_switch_release.py` retrieves the official pinned artifact; `init_live_stack.py` creates local secrets without printing them; `provision_live_demo.py` configures live identities/rooms. `live_room_context.py` must run with the runtime stopped to prevent socket takeover. Do not rerun approval/send scripts to demonstrate a completed workflow.

## Remaining limits and manual setup

No additional credential is needed for the verified local sandbox workflow. A signed official Switch Console 0.40.1 was installed under `.data/tools/SwitchConsole`; connecting its desktop UI is not verified. The official server/Gateway/Mattermost integration was verified independently.

The local demo agents are owned by the seeded Switch administrator, which the official server warns grants broad authority. Use a dedicated non-admin owner and narrower room policies before production. Bind endpoints locally; localhost deeplinks do not work from other machines. Production email, external calendar invitations and Google OAuth need separate real provider credentials and explicit configuration. AI outputs still need human review; the first draft's unsupported claims were caught during this run. Broader unfinished product features remain listed in the acceptance matrix.
