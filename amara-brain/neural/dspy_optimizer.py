"""
DSPy-powered prompt optimizer.
Pulls real decisions from Supabase, runs MIPROv2, saves improved prompts.
Only runs on agents with >= 10 decisions with known outcomes.
No synthetic data.
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path

import dspy

from neural import accuracy_tracker

_SUPABASE_URL = os.getenv("SUPABASE_URL", "")
_SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
_AGENTS_DIR = Path(__file__).parent.parent / "core" / "agents"
_LOG_PATH = Path(__file__).parent / "accuracy_log.csv"

lm = dspy.LM(
    model="openai/hermes3",
    api_base="http://127.0.0.1:18789/v1",
    api_key="none",
)
dspy.configure(lm=lm)


def _fetch_decisions(agent_id: str, limit: int = 30) -> list:
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        return []
    import requests
    try:
        resp = requests.get(
            f"{_SUPABASE_URL}/rest/v1/decision_log",
            headers={
                "apikey": _SUPABASE_KEY,
                "Authorization": f"Bearer {_SUPABASE_KEY}",
            },
            params={
                "select": "evidence_context,correct_answer,outcome",
                "agent_id": f"eq.{agent_id}",
                "outcome": "not.is.null",
                "order": "created_at.desc",
                "limit": str(limit),
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def _get_current_prompt_version(agent_dir: Path) -> int:
    versions = sorted(agent_dir.glob("prompt_v*.txt"))
    if not versions:
        return 0
    latest = versions[-1].stem
    try:
        return int(latest.replace("prompt_v", ""))
    except ValueError:
        return 0


def _save_optimized_prompt(agent_id: str, prompt_text: str) -> str:
    agent_dir = _AGENTS_DIR / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    version = _get_current_prompt_version(agent_dir) + 1
    prompt_file = agent_dir / f"prompt_v{version}.txt"
    prompt_file.write_text(prompt_text)
    registry_file = _AGENTS_DIR / "registry.json"
    registry = {}
    if registry_file.exists():
        with open(registry_file) as f:
            try:
                registry = json.load(f)
            except Exception:
                registry = {}
    registry[agent_id] = {
        "prompt_version": version,
        "prompt_file": str(prompt_file),
        "optimized_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(registry_file, "w") as f:
        json.dump(registry, f, indent=2)
    accuracy_tracker.log_inference(
        task_type="prompt_optimization",
        model="hermes3",
        tokens_in=0,
        tokens_out=0,
        agent_id=agent_id,
    )
    return str(prompt_file)


class AgentDecisionSignature(dspy.Signature):
    """Given evidence context, produce the correct agent analysis output."""
    evidence_context: str = dspy.InputField(desc="Evidence and context for the decision")
    analysis: str = dspy.OutputField(desc="Correct structured analysis output")


class AgentPredictor(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(AgentDecisionSignature)

    def forward(self, evidence_context: str) -> dspy.Prediction:
        return self.predict(evidence_context=evidence_context)


def optimize_agent(agent_id: str) -> str | None:
    """
    Pulls last 30 decisions with known outcomes for agent_id from Supabase.
    Runs MIPROv2. Saves improved prompt. Archives old prompt — never deletes.
    Returns new prompt text, or None if data is insufficient.
    """
    decisions = _fetch_decisions(agent_id, limit=30)
    decisions_with_outcomes = [
        d for d in decisions
        if d.get("outcome") and d.get("evidence_context") and d.get("correct_answer")
    ]

    if len(decisions_with_outcomes) < 10:
        log_msg = (
            f"{datetime.now(timezone.utc).isoformat()} | {agent_id} | "
            f"insufficient data ({len(decisions_with_outcomes)} decisions) — skipping optimization\n"
        )
        log_file = Path(__file__).parent / "logs" / "dspy_optimizer.log"
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, "a") as f:
            f.write(log_msg)
        return None

    trainset = [
        dspy.Example(
            evidence_context=d["evidence_context"],
            analysis=d["correct_answer"],
        ).with_inputs("evidence_context")
        for d in decisions_with_outcomes
    ]

    def accuracy_metric(example, pred, trace=None) -> float:
        expected = example.analysis.strip().lower()
        predicted = pred.analysis.strip().lower()
        if expected == predicted:
            return 1.0
        shared = set(expected.split()) & set(predicted.split())
        return len(shared) / max(len(expected.split()), 1)

    program = AgentPredictor()
    optimizer = dspy.MIPROv2(metric=accuracy_metric, auto="light")
    try:
        optimized = optimizer.compile(program, trainset=trainset)
        prompt_text = str(optimized.predict.signature)
        return _save_optimized_prompt(agent_id, prompt_text)
    except Exception as e:
        log_file = Path(__file__).parent / "logs" / "dspy_optimizer.log"
        with open(log_file, "a") as f:
            f.write(
                f"{datetime.now(timezone.utc).isoformat()} | {agent_id} | "
                f"optimization failed: {e}\n"
            )
        return None


def run_all_agents() -> None:
    """
    Optimizes every agent whose accuracy < 0.70 over last 30 decisions.
    Called by weekly_learning_run().
    """
    agents = ["Jade", "Red", "Dakota", "Oracle", "Geo"]
    for agent in agents:
        acc = accuracy_tracker.get_agent_accuracy(agent, last_n=30)
        if acc is not None and acc < 0.70:
            optimize_agent(agent)
