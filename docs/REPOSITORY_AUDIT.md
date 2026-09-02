# Repository Audit and Remediation Baseline

Date: 2026-09-02

## Scope reviewed

The review covered repository structure, authentication, the public Cloudflare Worker, local Compose configuration, reverse proxy settings, GitHub Actions, deployment documentation, and representative Python, Go, and React entry points.

## Corrected in this change

- Removed known fallback secrets from shared authentication and Compose.
- Required sufficiently long JWT and internal-service credentials.
- Changed internal key checks to constant-time comparison.
- Replaced predictable OTP generation and plaintext OTP storage with cryptographically secure generation and keyed digests.
- Raised the minimum password length to 12 characters.
- Replaced wildcard authenticated CORS with an explicit origin allowlist.
- Protected the Worker AI route with a bearer credential, request limits, upstream timeout handling, safe errors, and security headers.
- Stopped publishing PostgreSQL and Redis ports from the default Compose stack.
- Replaced CI jobs that ignored failures with blocking Python, Go, frontend, and Compose checks.
- Added isolated authentication tests and a security policy.
- Replaced sample credentials with generated-secret placeholders.

## Remaining release gates

These are explicit gates, not claims of completion:

- Add database migrations (Alembic or equivalent); remove runtime DDL and `create_all`.
- Store refresh-token identifiers and support rotation/revocation.
- Move rate limiting from process memory to Redis and use trusted-proxy configuration.
- Add foreign keys, uniqueness rules, tenant-isolation tests, and database backup/restore drills.
- Add end-to-end tests for edge → swarm → authority → dashboard and failure/retry behavior.
- Pin container images and GitHub Actions to immutable digests/commit SHAs.
- Add SBOM generation, signed images, provenance, and deployment admission policies.
- Review Kubernetes RBAC, pod security, network policies, persistent-volume encryption, and secret injection against the actual cluster.
- Threat-model libp2p identities, replay prevention, event signatures, reward/voting abuse, webhook SSRF, RTSP inputs, and LLM prompt/data exposure.
- Validate accessibility, browser support, performance budgets, retention/deletion controls, privacy notices, and regulated-industry claims.
- Remove or archive legacy and duplicate implementations only after migration tests identify the canonical service.

## Honest readiness level

The repository is suitable for controlled development and staging after configuration. It is not yet independently audited or ready for safety-critical, financial, medical, or regulated production use.
