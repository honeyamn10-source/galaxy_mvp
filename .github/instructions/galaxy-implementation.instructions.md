---
applyTo: "**"
description: "Use when implementing Galaxy services, interfaces, migration steps, and end-to-end integration."
---

Implementation policy for this repository:

1. Keep architecture coherent across Edge, Swarm, Authority, and Dashboard.
2. Prefer minimal diffs and avoid unrelated refactors.
3. Any new service must include:
   - container build definition
   - environment-variable configuration
   - health endpoint
   - actionable logs
4. Preserve interface compatibility during phase transitions by adding toggles where practical.
5. If a component contract changes, update setup docs and test flow in the same task.
6. Validate with available tooling:
   - syntax checks for Python/Go/JS where possible
   - diagnostics via editor errors
7. If runtime dependencies are missing on host, document exact missing commands and how to run checks on a machine with those dependencies.

Code quality rules:
- Avoid placeholders in committed flow paths.
- Keep security defaults strict for network boundaries.
- Use typed payload schemas.
- Handle malformed input and downstream failures explicitly.
