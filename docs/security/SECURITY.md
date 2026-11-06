# Security posture and remaining work

Implemented controls:

- Argon2id password hashes, opaque random session tokens stored as SHA-256 digests, HTTP-only SameSite cookies, expiry, logout revocation and revocation on role changes.
- Constant-time CSRF comparison for authenticated mutations, origin validation, restricted CORS and security headers. Production cookies use Secure and require HTTPS.
- Tenant-scoped queries, explicit membership/RBAC checks and validation of related customer/workflow ownership.
- Fernet encryption for agent keys, model keys and OAuth credentials. The key stays in server environment. Registration keys and agent keys are distinct. One-time registered agent credentials persist before addressing configuration.
- Pydantic validation, ORM parameterization, CSV formula neutralization, escaped document rendering, no raw HTML preview and no `dangerouslySetInnerHTML`.
- Upload-size/extension/signature checks, PDF page caps, DOCX expansion cap and explicit no-text/scanned-PDF errors.
- Exact-version/payload-hash approvals, conditional one-time human decisions, expiration, immutable generated versions and a unique external-execution claim. Agents cannot approve themselves.
- Customer opt-out and recipient-change checks at execution. SMTP is disabled until configured and production SMTP requires STARTTLS.
- Exact opaque participant mappings, addressed-event filtering, room checks, receipt deduplication, generation fencing and bounded handoff/model budgets.
- Models get fixed scoped context, no shell/filesystem/arbitrary HTTP tools, explicit external private-data consent and untrusted-content system instructions.
- Audit trail includes actors, resources, reasons, correlation IDs and failure records. API responses redact credential fields.

Known limitations requiring review before production:

- No email verification, password recovery, MFA, SSO or session management UI. Registration rate limiting is per API process; deploy shared edge rate limiting for multiple workers.
- No PostgreSQL row-level security, append-only DBA audit protection, formal threat model verification or penetration test. Application scoping is tested, not a substitute for independent review.
- File extraction runs in a limited thread with caps, not a restricted subprocess/container. PDFs may still contain adversarial complexity. Isolate extraction before processing untrusted external volumes.
- Trusted owner/admin endpoint configuration can reach private services by design for local Switch/Ollama. Untrusted agents/members cannot choose URLs. Add deployment-specific egress allowlists where administrators are not fully trusted.
- Prompt-injection instructions reduce risk but cannot guarantee model obedience. Deterministic server authorization prevents model content from authorizing sends.
- Runtime has one leader. A process crash around external I/O needs operator reconciliation. SMTP can accept a message and then fail the local response; it is never reported as confirmed delivery.
- Automatic data retention purge, encrypted backups, key rotation tooling, OAuth disconnect/revocation and complete lifecycle cleanup are not implemented.
- Owners manually attest Switch participant mappings. There is no automatic cryptographic account-linking ceremony or chat approval support.
- Gmail/email ingestion, external calendar invitation creation and generalized sensitive CRM/export/destructive approvals are not implemented. CSV export is manager-restricted and audited, but does not use the proposal approval engine.
- User-selected secrets can be blanked by an admin; secret values are never returned. Error strings from trusted local providers should be reviewed before exposing this to multiple organizations.
- The shipped production Compose overlay is a starting configuration; TLS, monitoring, backups, restore drills, shared rate limits and credential provisioning remain operator responsibilities.

Do not expose development servers or Mailpit/MinIO consoles to the public internet. Keep `.env`, database files, `.data`, virtual environments and all secrets out of source control.
