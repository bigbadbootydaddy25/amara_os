"""
deed/graph.py — Texhoma WV Title Examination LangGraph stack.

Five agents orchestrated in sequence (Well + Tax run in parallel after Chain):

    IDX_Agent
        ↓
    Chain_Builder_Agent
        ↓              ↓
    Well_Agent    Tax_Sheriff_Agent    ← parallel fan-out
        ↓              ↓
    OR_Builder_Agent  (fan-in)
        ↓
    Brain_Store_Node
        ↓
    END

Usage
-----
    from deed.graph import build_graph, DEFAULT_INPUT
    graph  = build_graph()
    result = graph.invoke(DEFAULT_INPUT)
    print(result["or_path"])

Or run directly:
    cd /Users/user/aegis_os && PYTHONPATH=. python3 deed/graph.py
"""
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("GRAPH")


# ══════════════════════════════════════════════════════════════════════════════
#  LangGraph imports — degrade gracefully if not installed
# ══════════════════════════════════════════════════════════════════════════════

try:
    from langgraph.graph import StateGraph, END
    _HAS_LANGGRAPH = True
except ImportError:
    _HAS_LANGGRAPH = False
    log.warning(
        "langgraph not installed — falling back to sequential runner. "
        "Install: pip install langgraph"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Agent node imports
# ══════════════════════════════════════════════════════════════════════════════

from deed.agents.idx           import run as idx_run
from deed.agents.chain_builder import run as chain_run
from deed.agents.well          import run as well_run_legacy
from deed.agents.tax_sheriff   import run as tax_run
from deed.agents.or_builder_agent import run as or_run
from deed.brain_store          import run as brain_run
from deed.state                import TitleState, DEFAULT_INPUT


# ── Well agent adapter (existing well.py uses positional config, not state) ──

def _well_node(state: TitleState) -> dict:
    """Adapts the existing well.py to the state-based LangGraph interface."""
    try:
        result = well_run_legacy()
        wells   = result.get("wells", [])
        status  = result.get("status", "COMPLETE")
        errors  = []
        if result.get("status") == "FAILED":
            errors = [f"WELL: {result.get('error', 'unknown error')}"]
        return {
            "wells":       wells,
            "well_count":  len(wells),
            "well_status": status,
            "errors":      errors,
        }
    except Exception as e:
        return {
            "wells":       [],
            "well_count":  0,
            "well_status": "FAILED",
            "errors":      [f"WELL: {e}"],
        }


# ── Brain store adapter ───────────────────────────────────────────────────────

def _brain_node(state: TitleState) -> dict:
    """Calls brain_store.run() with assembled results from state."""
    agent_results = {
        "IDX":           {"status": state.get("idx_status", "?"),   "count": len(state.get("idx_instruments") or [])},
        "CHAIN_BUILDER": {"status": state.get("chain_status", "?"), "count": len(state.get("chain") or [])},
        "WELL":          {"status": state.get("well_status", "?"),  "count": state.get("well_count", 0)},
        "TAX_SHERIFF":   {"status": state.get("tax_status", "?")},
        "OR_BUILDER":    {"status": state.get("or_status", "?"),    "path":  state.get("or_path", "")},
    }
    try:
        result = brain_run(agent_results, elapsed_s=0)
        return {"brain_results": result, "status": "COMPLETE"}
    except Exception as e:
        return {"brain_results": {"error": str(e)}, "errors": [f"BRAIN: {e}"]}


# ══════════════════════════════════════════════════════════════════════════════
#  Graph builder
# ══════════════════════════════════════════════════════════════════════════════

def build_graph():
    """
    Build and compile the LangGraph title examination graph.

    Topology:
        idx → chain_builder → [well || tax_sheriff] → or_builder → brain → END

    Parallel fan-out: LangGraph executes well and tax_sheriff concurrently
    after chain_builder completes. or_builder waits for both.
    """
    if not _HAS_LANGGRAPH:
        raise RuntimeError(
            "langgraph is required. Install: pip install langgraph\n"
            "Alternatively use run_sequential() for a plain Python execution."
        )

    g = StateGraph(TitleState)

    # ── Register nodes ────────────────────────────────────────────────────────
    g.add_node("idx",           idx_run)
    g.add_node("chain_builder", chain_run)
    g.add_node("well",          _well_node)
    g.add_node("tax_sheriff",   tax_run)
    g.add_node("or_builder",    or_run)
    g.add_node("brain",         _brain_node)

    # ── Edges ─────────────────────────────────────────────────────────────────
    g.set_entry_point("idx")
    g.add_edge("idx",           "chain_builder")

    # Fan-out: chain_builder → well AND tax_sheriff in parallel
    g.add_edge("chain_builder", "well")
    g.add_edge("chain_builder", "tax_sheriff")

    # Fan-in: both must complete before or_builder
    g.add_edge("well",          "or_builder")
    g.add_edge("tax_sheriff",   "or_builder")

    g.add_edge("or_builder",    "brain")
    g.add_edge("brain",         END)

    return g.compile()


# ══════════════════════════════════════════════════════════════════════════════
#  Sequential fallback (no LangGraph required)
# ══════════════════════════════════════════════════════════════════════════════

def run_sequential(initial_state: TitleState | None = None) -> TitleState:
    """
    Run all 5 agents sequentially without LangGraph.
    Identical results — use when langgraph is not installed.
    """
    state: TitleState = {**DEFAULT_INPUT, **(initial_state or {})}
    t0 = time.time()

    _banner("IDX Agent")
    state = {**state, **idx_run(state)}

    _banner("Chain Builder Agent")
    state = {**state, **chain_run(state)}

    _banner("Well Agent  +  Tax Sheriff Agent  (sequential fallback)")
    state = {**state, **_well_node(state)}
    state = {**state, **tax_run(state)}

    _banner("OR Builder Agent")
    state = {**state, **or_run(state)}

    _banner("Brain Store")
    state = {**state, **_brain_node(state)}

    elapsed = round(time.time() - t0)
    log.info("Pipeline complete in %ds | OR: %s", elapsed, state.get("or_path", "—"))
    _print_summary(state)
    return state


def _banner(name: str):
    log.info("─" * 60)
    log.info("  %-56s", name)
    log.info("─" * 60)


def _print_summary(state: TitleState):
    print("\n" + "═" * 64)
    print("  TEXHOMA WV TITLE EXAMINATION — COMPLETE")
    print("═" * 64)
    print(f"  Parcel     : {state.get('parcel_id')}")
    print(f"  IDX        : {state.get('idx_status')} "
          f"({len(state.get('idx_instruments') or [])} instruments)")
    print(f"  Chain      : {state.get('chain_status')} "
          f"({len(state.get('chain') or [])} ordered)")
    print(f"  Wells      : {state.get('well_status')} "
          f"({state.get('well_count', 0)} found)")
    print(f"  Tax        : {state.get('tax_status')} "
          f"| Ticket {(state.get('tax_surface') or {}).get('ticket_no', '—')}")
    print(f"  OR         : {state.get('or_status')} → {state.get('or_path', '—')}")
    if state.get("errors"):
        print(f"  Errors     : {len(state['errors'])}")
        for e in state["errors"]:
            print(f"    ✗ {e}")
    print("═" * 64 + "\n")


# ══════════════════════════════════════════════════════════════════════════════
#  CLI entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Texhoma WV Title Examination Stack")
    ap.add_argument("--parcel",   default="11-409-19", help="Tax parcel ID")
    ap.add_argument("--langgraph", action="store_true",
                    help="Use LangGraph orchestration (default: sequential)")
    args = ap.parse_args()

    override = {}
    if args.parcel != "11-409-19":
        override["parcel_id"] = args.parcel

    if args.langgraph and _HAS_LANGGRAPH:
        log.info("Running via LangGraph graph.invoke()")
        graph  = build_graph()
        result = graph.invoke({**DEFAULT_INPUT, **override})
        _print_summary(result)
    else:
        if args.langgraph and not _HAS_LANGGRAPH:
            log.warning("--langgraph requested but langgraph not installed — using sequential")
        run_sequential(override or None)
