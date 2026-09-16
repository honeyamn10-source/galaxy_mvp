# ADR-0001 — Use an Architecture Decision Record (ADR) convention

- **Status:** Accepted
- **Date:** 2026-09-16
- **Applies to:** this repository's architecture documentation

## Context
Galaxy is a polyglot decentralized AI platform (Go, TypeScript/React, Python, Rust/GoWasm, k8s). Big design decisions — swarm topology, authority chain rewards, compliance, federated learning, LLM wiring — need a low-friction written record so contributors see *why* we chose the way we did, and reviewers can challenge the "why" without re-deriving it.

## Decision
Every consequential, hard-to-reverse decision gets a numbered record in `docs/decisions/ADR-NNNN-title.md`, following MADR-lite:
- Context → Decision → Consequences (positive + negative) → Alternatives considered.
- Keep each ADR to one decision, ~300–500 words.
- Reference the decision everywhere it matters (README, PHASE docs) with a short link.

## Consequences
+ Clear "why" trail; cheap to review in PRs; ADRs double as onboarding reading.
− Requires discipline to actually write them; risk of drift if skipped.
CHANGED
EOF
# --- ADR 0005: many-agent team collaboration backbone ---
cat > docs/decisions/0005-many-agent-team-collaboration.md <<'D5EOF'
# ADR-0005 — Many-agent team collaboration as the core of Galaxy "universal" capability

- **Status:** Accepted
- **Date:** 2026-09-16
- **Scope:** permission-led, loopback-only, decentralized AI event-detection platform

## Context
The platform detects and reacts to events "universally across fields" (industry, compliance, care, ops — not just cameras). We want Galaxy to work like a group of people — a team — where specialist members collaborate instead of one do-everything program. Naive approaches: a single monolithic agent (becomes a jack-of-all-trades with weak governance), or unbounded agent networks (uncontrollable, unsafe, spreads sensitive data).

The safety frame is fixed in this repo:
- Everything agent-y runs **loopback-only** (127.0.0.1) behind an auth boundary.
- No **unauthenticated** remote usage, no internet-roaming agents, no free-floating surveillance.
- Every risky action is **permission-led** (explicit allow / deny / ask-approval; approval gates).

## Decision
Model Galaxy's agent intelligence as **one team of collaborating, permission-led specialist agents** rather than a single universal agent or an unbounded network:

1. **Specialist members in roles** (not generic agents):
   - `event-guard` — ingests and validates edge events (device + telemetry).
   - `authority-verifier` — signs off events along the authority chain (verification + voting).
   - `compliance-analyzer` — checks events against policies; flags approvals; drives the compliance engine + webhooks.
   - `fl-coordinator` — federated learning member-aggregation (privacy-preserving model updates).
   - `risk-predictor` — predictive service over aggregated intelligence.
   - `llm-consultant` — DeepSeek/LLM analysis; makes Json-language recommendations in plain text for human review.
   - `team-lead` — orchestrates members: plans, assigns, merges results, escalates to human approval; the only member that talks to the Dashboard.

2. **A single "team-lead" orchestrator** is the only collaborator with permission to emit user-visible, execution-relevant outputs — mirroring how a lead routes work to specialists and reports up. Members never talk directly to the public UI; they talk to the team-lead over an internal (loopback, authenticated) message bus.

3. **Universal across fields = many roles, guardrails per role.** Adding a new field (e.g., energy audit, patient vitals, quality control) = adding/reusing role-specialists, not weakening the safety frame. Each role still runs loopback, is permission-led, and is deployed with the same approval gates. "Works for anything" is achieved by breadth of governed collaborators — never by removing oversight.

4. **Collaboration contract:** members exchange only *event + decision + approval tokens* over a loopback bus; they never expose raw tenant data to each other beyond what the authority chain already scopes. Consensus/majority between members (verifier × compliance × risk) is required before team-lead may emit a high-impact decision.

## Consequences
+ Team shape scales to "many fields" while keeping one safety frame; specialist roles are individually reviewable and testable; human-in-the-loop approval rides on every high-impact action; matches how a real multi-disciplinary crew operates.
− More moving parts than a single agent (need a message bus + role registry + per-role permissions); team-lead is a collaboration hot-spot and must be the most-permission-restricted surface; requires discipline to avoid role creep.

## Alternatives considered
- Single universal agent → reject: weak governance, harder to make permission-led per action.
- Unbounded public agent network → reject: violates loopback-only + no-internet-roaming + no-unauthenticated policy.
- Camera-only specialization → reject: user wants universal fields, so we generalize via many roles instead of one vertical.

## Resulting roadmap hooks
- `docs/decisions/ADR-0005` is the "why" behind the team-collaboration pillar.
- Next: team-lead orchestrator + role registry + loopback bus, seeded as hermetic, permission-led tests (same pattern as Phase I tests).
D5EOF
echo "ADRs written:"; ls docs/decisions/
