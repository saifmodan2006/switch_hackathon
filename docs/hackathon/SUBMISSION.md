# SwitchOps AI

**Category:** Best Business Workflow
**Tagline:** Your AI Workforce. Your Team. One Command Center.

## Problem

Business work spans customer records, internal research, proposals, approvals and follow-up. Disconnected agents and invisible handoffs make it hard to establish context, accountability and authorization.

## Solution

A cohesive business command center around genuine Switch Rooms: six specialist identities collaborate visibly, while a tenant-scoped database persists customers, workflow state, versioned artifacts and human decisions. An exact human-approved proposal can be sent through configured SMTP and followed by an internal scheduling handoff.

## Technology

Next.js App Router, strict TypeScript, React, Tailwind, shadcn-style Radix components, TanStack Query, Zustand, React Hook Form/Zod, Recharts, Motion, FastAPI, Pydantic, SQLAlchemy async, Alembic, PostgreSQL/pgvector (SQLite for local development), Switch WebSocket/HTTP protocol, Ollama/OpenAI-compatible inference, Redis/ARQ, MinIO and Mailpit. Source and dependency license notes are in `docs/DEPENDENCIES.md`.

## Role of Switch

Switch supplies shared rooms, agent identities, addressing, persistent collaboration history and Mattermost bridging. Every specialist handoff is a genuine room message and addressed event. A disconnected Switch blocks new collaboration. Business persistence and human approval stay in the application database.

## Main functions

CRM, command requests, workflow timelines, six agents, real connection indicators, versioned proposals/PDFs, exact-payload approval, SMTP acceptance tracking, internal follow-up tasks/calendar, knowledge retrieval, business analytics, team roles and audit history.

## Reproduce

Follow README setup and `switch/onboarding/README.md`, then run `docs/hackathon/DEMO_SCRIPT.md`. The deterministic test suite is explicitly separate from a live Switch/LLM demo. Local business functions and test-double pipeline have been exercised; live service validation is still required.

## Submission links

- Repository: https://github.com/saifmodan2006/switch_hackathon
- Live deployment: **not deployed — add only after deployment verification**
- Video: **not recorded — add only after recording the actual live demonstration**

## Limitations

See `docs/ACCEPTANCE.md` and `docs/VERIFICATION.md`. No real Switch server, Mattermost bridge, LLM inference, Docker startup or Mailpit capture was verified in the available environment. Secondary scope remains incomplete, including external email ingestion, Gmail OAuth, sending Google invitations, generalized approvals, automated retention and document visual diffs. Do not describe this build as fully production operational until these limits and the live acceptance run are resolved.
