# Security Policy

## Supported branch

Security fixes target the default branch. Deploy only a tagged release whose CI and security workflows pass.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's **Security → Report a vulnerability** private reporting flow. Include the affected component, reproduction steps, impact, and any suggested mitigation. Do not include production credentials or personal data.

## Deployment requirements

- Generate unique values for `JWT_SECRET`, `INTERNAL_API_KEY`, `EDGE_TENANT_API_KEY`, `DEFAULT_EDGE_API_KEY`, `POSTGRES_PASSWORD`, `COMPLIANCE_ENCRYPTION_KEY`, and Worker `AI_API_KEY`.
- Store secrets in the deployment platform's secret manager; never commit `.env`, certificates, database exports, or API tokens.
- Terminate TLS at a trusted ingress and restrict internal services to private networks.
- Keep PostgreSQL and Redis unpublished. The default Compose file exposes only application endpoints.
- Set `ALLOWED_ORIGINS` to the exact dashboard origins. Wildcard CORS is not supported for authenticated endpoints.
- Rotate credentials immediately if a secret is logged or committed.
- Enable GitHub secret scanning, push protection, Dependabot alerts, and branch protection requiring CI.

Generate local secrets with `openssl rand -hex 32`. Copy `.env.example` to `.env` and replace every angle-bracket placeholder before startup.

## Security boundaries

This repository is an application scaffold, not a certified blockchain, medical device, safety system, or compliance product. Event signatures, model results, reward logic, and audit records require threat modeling and independent review before production or regulated use.

## Incident response

1. Isolate the affected service.
2. Revoke API keys and rotate signing, JWT, database, SMTP, provider, and internal-service credentials.
3. Preserve relevant logs and database snapshots.
4. Patch on a private branch and validate the complete event path.
5. Notify affected users and regulators when legally required.
