#!/usr/bin/env bash
set -euo pipefail

WORKDIR="${WORKDIR:-$(cd "$(dirname "$0")/.." && pwd)}"

cd "$WORKDIR/contracts"

if ! command -v cargo >/dev/null 2>&1; then
  echo "cargo is not installed. Install Rust toolchain to run contract tests."
  exit 1
fi

cargo test --workspace --lib
