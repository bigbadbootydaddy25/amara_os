#!/usr/bin/env bash
# AI_BRAIN Neuron Network — direct runner
# Usage: bash agents/neuron-network/connect_now.sh [args]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$ROOT"
exec python3 agents/neuron-network/run.py "$@"
