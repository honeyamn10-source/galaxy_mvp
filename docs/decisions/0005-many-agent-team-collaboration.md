# ADR-0005 — Many-agent team collaboration as the universal-capability backbone

- **Status:** Accepted
- **Date:** 2026-09-16
- **Scope:** permission-led, loopback-only, decentralized AI event-detection platform

## Context
The platform should detect and react to events *universally, across many fields* — not just one (e.g., not only cameras). A single do-everything agent becomes a weak, ungoverned jack-of-all-trades; an unbounded agent network becomes uncontrollable and leaks tenant data. The safety frame of this repo is fixed: everything agent-y runs **loopback-only**, no **unauthenticated** remote control, no free-roaming surveillance, and every risky action is **approval-gated**.

## Decision
Model Galaxy's intelligence as **a team of many collaborating, permission-led specialist agents** rather than one universal monolith:

1. **Specialist roles that behave like a crew** (allowed, permission-led members):
   - `event-guard` - ingests + validates edge events (device, tenant, telemetry).
   - `authority-verifier` - signs off events along the authority chain (chained verification + voting).
   - `compliance-engine` - checks events vs policies; flags approval; drives webhooks/CSV-out.
   - `fl-coordinator` - federated-learning member aggregation (privacy-preserving updates).
   - `risk-predictor` - predictive risk scoring over aggregated intelligence.
   - `llm-consultant` - optional LLM (DeepSeek/Ollama) analysis, output as *suggestions for human review*.
   - `team-lead` - orchestrates the crew: plans -> assigns -> verifies -> escalates to human approval. **The only member that talks to the dashboard.**

2. **Communication**: members collaborate over the loopback message bus; each role has narrowly-scoped read/write permissions to the authority chain; no role can reach beyond loopback or take an action without approval.

3. **"Universal across fields" = breadth of governed roles, not fewer guards.** Adding a field (energy audit, patient vitals, quality control, ops telemetry) means adding/reusing specialist roles — never weakening the safety frame.

## Consequences
+ Team shape is reviewable and testable per-role; single-lead approval surface is small and auditable; scales to many fields with one consistent safety model.
- More moving parts than one agent; team-lead is a hot-spot and must be the most permission-restricted surface; needs role registry + message bus to avoid role creep.

## Alternatives considered
- Single universal agent (chosen against: weak governance, hard to review).
- Unbounded open agent network (chosen against: violates loopback-only + no-unauthenticated policy).
- Camera-only specialization (chosen against: user wants universal fields; we generalize via many roles).
