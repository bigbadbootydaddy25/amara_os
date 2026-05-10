#!/usr/bin/env bash
# AI_BRAIN — Run Neuron Network health check and print the top-level report.
# Usage: bash scripts/run_neuron_network.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo ""
echo "Running AI_BRAIN Neuron Network..."
echo ""

python3 agents/neuron-network/run.py "$@"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  reports/NEURON_NETWORK_STATUS.md"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
cat reports/NEURON_NETWORK_STATUS.md
