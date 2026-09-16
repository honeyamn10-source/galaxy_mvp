# ADR-0002: Loopback-Only Serving

- Status: Accepted
- Date: 2026-09-16
- Deciders: Bittu Sharma, CI

## Context
The Galaxy MVP platform includes multiple interactive demos and UIs. To maintain
security and reproducibility, all demos must serve exclusively on loopback
interfaces (127.0.0.1). No unauthenticated remote access is permitted.

## Decision
All HTTP servers in demos, landing pages, and interactive UIs bind to
127.0.0.1 only. CI runs all integration tests against localhost. No public
interface defaults are allowed in any component.

## Consequences
- Reproducible demos: every screenshot is an honest loopback capture
- Security: zero attack surface from unauthenticated remote connections
- Portfolio-wide invariant: matches jawa-quant-computer ADR-0002 and
  quant-lab ADR-0002 for consistent safety posture
