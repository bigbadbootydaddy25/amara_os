"""
DSPy-powered prompt optimizer.
Attempts to import from OpenJarvis if available, then falls back to
direct DSPy MIPROv2 implementation.
Only optimizes on real outcomes — never synthetic data.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_AMARA_BRAIN = Path(os.getenv("AMARA_BRAIN", str(Path(__file__).parent.parent / "Brain")))
_OUTCOMES_FILE = _AMARA_BRAIN / "Outcomes" / "outcomes.jsonl"
_AGENTS_DIR = Path(__file__).parent.parent / "core" / "agents"
_LOG_DIR = _AMARA_BRAIN / "Logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# Attempt to use OpenJarvis optimizer if available on this machine
_OPENJARVIS_PATH = Path(
    os.getenv("OPENJARVIS_PATH", "/Users/user/OpenJarvis/src")
)
_openjarvis_available = False
if _OPENJARVIS_PATH.exists() and str(_OPENJARVIS_PATH) not in sys.path:
    sys.path.insert(0, str(_OPENJARVIS_PATH))
    try:
        from openjarvis.learning.agents.dspy_optimizer import optimize as _oj_optimize
        _openjarvis_available = True
        log.info("OpenJarvis dspy_optimizer loaded from %s", _OPENJARVIS_PATH)
    except ImportError:
        _openjarvis_available = False

# Configure DSPy with OpenClaw endpoint
_dspy_configured = False
try:
    import dspy
    _lm = dspy.LM(
        model="openai/hermes3",
        api_base=os.getenv("OPENCLAW_BASE_URL", "http://127.0.0.1:18789") + "/v1",
        api_key=os.getenv("OPENCLAW_API_KEY", "none"),
    )
    dspy.configure(lm=_lm)
    _dspy_configured = True
except Exception as e:
    log.warning("DSPy configuration failed: %s — optimization will be skipped", e)


def _load_outcomes_for_agent(agent_id: str, limit: int = 30) -> list:
    """Loads real outcomes from JSONL file. No synthetic data."""
    if not _OUTCOMES_FILE.exists():
        return []
    entries = []
    with open(_OUTCOMES_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if (
                    entry.get("agent_id") == agent_id
                    and entry.get("outcome") in {"CORRECT", "INCORRECT", "PARTIAL"}
                    and entry.get("evidence_context")
                    and entry.get("correct_answer")
                ):
                    entries.append(entry)
            except json.JSONDecodeError:
                continue
    return entries[-limit:]


def _get_prompt_version(agent_dir: Path) -> int:
    versions = sorted(agent_dir.glob("prompt_v*.txt"))
    if not versions:
        return 0
    try:
        return int(versions[-1].stem.replace("prompt_v", ""))
    except ValueError:
        return 0


def _save_prompt(agent_id: str, prompt_text: str) -> Path:
    agent_dir = _AGENTS_DIR / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    version = _get_prompt_version(agent_dir) + 1
    out = agent_dir / f"prompt_v{version}.txt"
    out.write_text(prompt_text)

    registry = _AGENTS_DIR / "registry.json"
    data = {}
    if registry.exists():
        try:
            data = json.loads(registry.read_text())
        except Exception:
            data = {}
    data[agent_id] = {
        "prompt_version": version,
        "prompt_file": str(out),
        "optimized_at": datetime.now(timezone.utc).isoformat(),
    }
    registry.write_text(json.dumps(data, indent=2))
    return out


def optimize_agent(agent_id: str) -> str | None:
    """
    Optimizes the system prompt for agent_id using real outcome data.
    Returns path to new prompt file, or None if data is insufficient or
    optimization infrastructure is unavailable.
    Skips silently if fewer than 10 real outcomes with evidence context.
    """
    outcomes = _load_outcomes_for_agent(agent_id, limit=30)
    if len(outcomes) < 10:
        msg = (
            f"{datetime.now(timezone.utc).isoformat()} | {agent_id} | "
            f"insufficient data ({len(outcomes)} usable outcomes) — skipping\n"
        )
        with open(_LOG_DIR / "dspy_optimizer.log", "a") as f:
            f.write(msg)
        log.info("Skipping optimization for %s: %d outcomes < 10 minimum", agent_id, len(outcomes))
        return None

    if _openjarvis_available:
        try:
            prompt_text = _oj_optimize(agent_id=agent_id, outcomes=outcomes)
            saved = _save_prompt(agent_id, prompt_text)
            log.info("OpenJarvis optimization complete for %s -> %s", agent_id, saved)
            return str(saved)
        except Exception as e:
            log.warning("OpenJarvis optimization failed for %s: %s — trying DSPy directly", agent_id, e)

    if not _dspy_configured:
        msg = (
            f"{datetime.now(timezone.utc).isoformat()} | {agent_id} | "
            "DSPy not configured (OpenClaw unavailable) — skipping\n"
        )
        with open(_LOG_DIR / "dspy_optimizer.log", "a") as f:
            f.write(msg)
        log.warning("DSPy not configured — cannot optimize %s", agent_id)
        return None

    try:
        class AgentSignature(dspy.Signature):
            """Given evidence context, produce correct structured analysis."""
            evidence_context: str = dspy.InputField(desc="Evidence and context for the decision")
            analysis: str = dspy.OutputField(desc="Correct structured analysis output")

        class AgentPredictor(dspy.Module):
            def __init__(self):
                self.predict = dspy.Predict(AgentSignature)

            def forward(self, evidence_context: str) -> dspy.Prediction:
                return self.predict(evidence_context=evidence_context)

        trainset = [
            dspy.Example(
                evidence_context=o["evidence_context"],
                analysis=o["correct_answer"],
            ).with_inputs("evidence_context")
            for o in outcomes
        ]

        def accuracy_metric(example, pred, trace=None) -> float:
            expected = example.analysis.strip().lower()
            predicted = pred.analysis.strip().lower()
            if expected == predicted:
                return 1.0
            shared = set(expected.split()) & set(predicted.split())
            return len(shared) / max(len(expected.split()), 1)

        optimizer = dspy.MIPROv2(metric=accuracy_metric, auto="light")
        optimized = optimizer.compile(AgentPredictor(), trainset=trainset)
        prompt_text = str(optimized.predict.signature)
        saved = _save_prompt(agent_id, prompt_text)
        log.info("DSPy MIPROv2 optimization complete for %s -> %s", agent_id, saved)
        return str(saved)

    except Exception as e:
        with open(_LOG_DIR / "dspy_optimizer.log", "a") as f:
            f.write(
                f"{datetime.now(timezone.utc).isoformat()} | {agent_id} | "
                f"optimization error: {e}\n"
            )
        log.error("Optimization failed for %s: %s", agent_id, e)
        return None


def run_all_agents() -> None:
    """Runs optimize_agent for all agents below 0.70 accuracy."""
    from neural.feedback_loop import get_agent_accuracy
    agents = ["Jade", "Red", "Dakota", "Oracle", "Geo"]
    for agent in agents:
        acc = get_agent_accuracy(agent, last_n=30)
        if acc is not None and acc < 0.70:
            optimize_agent(agent)
