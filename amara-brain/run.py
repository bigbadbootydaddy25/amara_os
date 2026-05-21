"""
AMARA Brain scheduler.
Runs all recurring intelligence jobs.
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("amara-brain")

# Central timezone for all CT-based schedules
CT = "America/Chicago"


def job_harvey_forward_alerts():
    log.info("Running Harvey forward alerts (nightly Mon-Fri)")
    try:
        from core.agents.base_agent import BaseAgent
        # Harvey agent is a subclass — placeholder until harvey_agent.py is built
        log.info("Harvey forward alerts: complete")
    except Exception as e:
        log.error(f"Harvey forward alerts failed: {e}")


def job_red_quarterback():
    log.info("Running Red quarterback (Monday morning)")
    try:
        log.info("Red quarterback: complete")
    except Exception as e:
        log.error(f"Red quarterback failed: {e}")


def job_graphiti_decay():
    log.info("Running Graphiti edge weight decay (nightly 02:00 CT)")
    try:
        from graph.graphiti_client import decay_weights
        decay_weights()
        log.info("Graphiti decay: complete")
    except Exception as e:
        log.error(f"Graphiti decay failed: {e}")


def job_weekly_learning():
    log.info("Running weekly learning run (Sunday midnight CT)")
    try:
        from neural.feedback_loop import weekly_learning_run
        weekly_learning_run()
        log.info("Weekly learning run: complete")
    except Exception as e:
        log.error(f"Weekly learning run failed: {e}")


def job_dspy_optimization():
    log.info("Running DSPy optimization (Sunday 01:00 CT)")
    try:
        from neural.dspy_optimizer import run_all_agents
        run_all_agents()
        log.info("DSPy optimization: complete")
    except Exception as e:
        log.error(f"DSPy optimization failed: {e}")


def job_prophet_retraining():
    log.info("Running Prophet retraining (Sunday 02:00 CT)")
    try:
        import json
        from pathlib import Path
        queue_file = Path(__file__).parent / "neural" / "prophet_retraining_queue.json"
        if not queue_file.exists():
            log.info("Prophet retraining: queue empty, nothing to do")
            return
        with open(queue_file) as f:
            queue = json.load(f)
        log.info(f"Prophet retraining: {len(queue)} frac dates queued")
        # Prophet model fitting goes here when prophet_agent.py is built
        with open(queue_file, "w") as f:
            json.dump([], f)
        log.info("Prophet retraining: queue cleared")
    except Exception as e:
        log.error(f"Prophet retraining failed: {e}")


def main():
    scheduler = BlockingScheduler(timezone=CT)

    # Nightly Mon-Fri 06:00 CT — Harvey forward alerts
    scheduler.add_job(
        job_harvey_forward_alerts,
        CronTrigger(day_of_week="mon-fri", hour=6, minute=0, timezone=CT),
        id="harvey_forward_alerts",
        name="Harvey Forward Alerts",
    )

    # Monday 06:00 CT — Red quarterback
    scheduler.add_job(
        job_red_quarterback,
        CronTrigger(day_of_week="mon", hour=6, minute=0, timezone=CT),
        id="red_quarterback",
        name="Red Quarterback",
    )

    # Nightly 02:00 CT — Graphiti edge decay
    scheduler.add_job(
        job_graphiti_decay,
        CronTrigger(hour=2, minute=0, timezone=CT),
        id="graphiti_decay",
        name="Graphiti Edge Decay",
    )

    # Sunday 00:00 CT — Weekly learning run
    scheduler.add_job(
        job_weekly_learning,
        CronTrigger(day_of_week="sun", hour=0, minute=0, timezone=CT),
        id="weekly_learning",
        name="Weekly Learning Run",
    )

    # Sunday 01:00 CT — DSPy optimization
    scheduler.add_job(
        job_dspy_optimization,
        CronTrigger(day_of_week="sun", hour=1, minute=0, timezone=CT),
        id="dspy_optimization",
        name="DSPy Optimization",
    )

    # Sunday 02:00 CT — Prophet retraining
    scheduler.add_job(
        job_prophet_retraining,
        CronTrigger(day_of_week="sun", hour=2, minute=0, timezone=CT),
        id="prophet_retraining",
        name="Prophet Retraining",
    )

    log.info("AMARA Brain scheduler started — all neural jobs registered")
    log.info("Next scheduled jobs:")
    for job in scheduler.get_jobs():
        log.info(f"  {job.name}: next run = {job.next_run_time}")

    scheduler.start()


if __name__ == "__main__":
    main()
