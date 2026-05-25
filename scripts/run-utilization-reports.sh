#!/usr/bin/env bash
set -euo pipefail

# Backward-compatible wrapper. The canonical report CLI is report.sh.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

exec "${REPO_ROOT}/report.sh" --comparison --report utilization "$@"
