# Monitoring entry points

- `GET /api/v1/health` checks SQL reachability and reports the application version.
- `GET /api/v1/switch/status` is authenticated and derives agent connectivity from recent persisted heartbeat timestamps.
- JSON request logs contain method, route, status and correlation ID; they do not log credentials or full request payloads.
- Workflow detail exposes durable events, failures, citations and room references. `/api/v1/audit` exposes the latest tenant-scoped audit trail.
- `agent_messages.status=failed` and its error/attempt count are the durable failed-event inspection store. A dedicated dead-letter recovery UI is not implemented.
- `email_deliveries` distinguishes claimed, sandbox_accepted, smtp_accepted and unknown_or_failed. Reconcile unknown outcomes with the actual provider before any retry.
- ARQ worker health is checked by Compose; Postgres/Redis/API/web have health checks. MinIO and agents use their service logs and application heartbeat signals.

For production attach your log collector, persistent alerting, metrics exporter, uptime probes and backup/restore monitoring. OpenTelemetry API is a dependency of the installed FastAPI release, but no full collector/exporter instrumentation is claimed here.
