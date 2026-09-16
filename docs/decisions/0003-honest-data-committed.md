# ADR-0003: Honest Data, Committed

- Status: Accepted
- Date: 2026-09-16
- Deciders: Bittu Sharma, CI

## Context
AI/ML platforms often report metrics backed by tuned screenshots or cherry-picked
runs. The Galaxy MVP must demonstrate reproducible, honest results.

## Decision
Every reported metric, screenshot, and benchmark traces to committed, versioned
data and code. Screenshots are captured from real loopback executions during CI,
never fabricated. All ML/federated learning results are regenerated from
committed seeds.

## Consequences
- Zero fabricated metrics in README, docs, or marketing
- CI regenerates screenshots on every push (see scripts/capture_screenshots.py)
- Federated learning runs use committed seeds for reproducibility
- Matches portfolio-wide standard set in jawa-quant-computer ADR-0003
