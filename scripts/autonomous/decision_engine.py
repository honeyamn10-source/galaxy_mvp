#!/usr/bin/env python3
import json
import os
from pathlib import Path
from typing import TypedDict


class Decision(TypedDict):
    action: str
    reason: str


class Check(TypedDict):
    id: str
    path: Path
    reason: str


ROOT = Path(__file__).resolve().parents[2]


def decide() -> Decision:
    checks: list[Check] = [
        {
            "id": "add_dependabot",
            "path": ROOT / ".github" / "dependabot.yml",
            "reason": "missing Dependabot updates for supply-chain hardening",
        },
        {
            "id": "add_worker_ci_trigger",
            "path": ROOT / ".github" / "workflows" / "cloudflare-worker.yml",
            "reason": "missing dedicated worker deployment workflow",
        },
    ]

    for item in checks:
        if not item["path"].exists():
            return {
                "action": item["id"],
                "reason": item["reason"],
            }

    return {
        "action": "noop",
        "reason": "no deterministic low-risk improvements pending",
    }


if __name__ == "__main__":
    decision = decide()
    print(json.dumps(decision))
    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"action={decision['action']}\n")
            f.write(f"reason={decision['reason']}\n")
