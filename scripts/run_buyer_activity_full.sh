#!/usr/bin/env bash
# Full buyer-activity pipeline.
#
# Usage:
#   bash scripts/run_buyer_activity_full.sh [WORKSPACE_ROOT]
#
# WORKSPACE_ROOT defaults to the repository root (parent of this script's
# directory).  Pass an explicit path to run against a different workspace:
#   bash scripts/run_buyer_activity_full.sh /Users/user/ai-brain

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_ROOT="${1:-$REPO_ROOT}"

AGENT_DIR="$REPO_ROOT/agents/buyer-activity-osint"
WRITER="$AGENT_DIR/tools/write_purchase_history_outputs.py"
REPORTS_DIR="$AGENT_DIR/reports"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  buyer-activity full pipeline"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  workspace : $WORKSPACE_ROOT"
echo "  reports   : $REPORTS_DIR"
echo ""

# ── Step 1: ingest CSVs, build profiles, write ACTIVITY_SUMMARY.json ─────────
echo "── Step 1: run.py (ingest + profile)"
python3 "$AGENT_DIR/run.py" \
    --workspace-root "$WORKSPACE_ROOT" \
    --reports-dir    "$REPORTS_DIR"

# ── Step 2: write purchase-history and heat-ranking files ─────────────────────
echo ""
echo "── Step 2: write_purchase_history_outputs.py"
python3 "$WRITER" \
    --reports-dir "$REPORTS_DIR"

# ── Step 3: verify all six expected files exist ───────────────────────────────
echo ""
echo "── Step 3: verify output files"

EXPECTED=(
    "BUYER_PURCHASE_HISTORY.md"
    "RECENT_BUYERS.json"
    "MULTI_PURCHASE_BUYERS.json"
    "BUYER_HEAT_RANKINGS.md"
    "HOT_BUYERS.json"
    "ACTIVE_BUYERS.json"
)

ALL_OK=true
for FILE in "${EXPECTED[@]}"; do
    PATH_TO_CHECK="$REPORTS_DIR/$FILE"
    if [[ -f "$PATH_TO_CHECK" ]]; then
        SIZE=$(wc -c < "$PATH_TO_CHECK")
        echo "  ✓  $FILE  (${SIZE} bytes)"
    else
        echo "  ✗  MISSING: $FILE"
        ALL_OK=false
    fi
done

echo ""
if [[ "$ALL_OK" == "true" ]]; then
    echo "All six files present.  Pipeline complete."
    echo "Reports: $REPORTS_DIR/"
else
    echo "ERROR: one or more expected files are missing." >&2
    exit 1
fi
