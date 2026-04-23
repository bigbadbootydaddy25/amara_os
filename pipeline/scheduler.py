"""
Pipeline scheduler — sets up a daily cron job to run the full pipeline.

Two modes:
  1. Install mode: writes a crontab entry that runs pipeline.py daily at 2am
  2. Run mode: executes a single pipeline pass (used by cron)

Usage:
    # Install the daily cron job
    cd /home/user/amara_os/pipeline
    python scheduler.py --install

    # Remove the cron job
    python scheduler.py --remove

    # Run once (called by cron)
    python scheduler.py --run
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent
PYTHON       = sys.executable
PIPELINE_CMD = f"cd {PIPELINE_DIR} && {PYTHON} pipeline.py"
CRON_COMMENT = "# real-estate-osint-pipeline"
CRON_TIME    = "0 2 * * *"  # daily at 2:00am
CRON_LINE    = f"{CRON_TIME} {PIPELINE_CMD} >> {PIPELINE_DIR}/logs/cron.log 2>&1 {CRON_COMMENT}"


def get_existing_crontab() -> str:
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else ""
    except FileNotFoundError:
        print("ERROR: crontab not available on this system")
        sys.exit(1)


def install_cron():
    existing = get_existing_crontab()
    if CRON_COMMENT in existing:
        print("Cron job already installed.")
        return
    new_crontab = existing.rstrip() + f"\n{CRON_LINE}\n"
    proc = subprocess.run(
        ["crontab", "-"],
        input=new_crontab,
        text=True,
        capture_output=True,
    )
    if proc.returncode == 0:
        print(f"Cron job installed: runs daily at 2:00am")
        print(f"  Command: {PIPELINE_CMD}")
        print(f"  Log:     {PIPELINE_DIR}/logs/cron.log")
    else:
        print(f"Failed to install cron job: {proc.stderr}")
        sys.exit(1)


def remove_cron():
    existing = get_existing_crontab()
    if CRON_COMMENT not in existing:
        print("No cron job found to remove.")
        return
    new_lines = [
        line for line in existing.splitlines()
        if CRON_COMMENT not in line and line.strip()
    ]
    new_crontab = "\n".join(new_lines) + "\n"
    proc = subprocess.run(
        ["crontab", "-"],
        input=new_crontab,
        text=True,
        capture_output=True,
    )
    if proc.returncode == 0:
        print("Cron job removed.")
    else:
        print(f"Failed to remove cron job: {proc.stderr}")


def run_once():
    """Execute the pipeline directly (used when called by cron)."""
    os.chdir(PIPELINE_DIR)
    sys.path.insert(0, str(PIPELINE_DIR))
    from pipeline import main
    main()


def main():
    parser = argparse.ArgumentParser(description="Pipeline scheduler")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true", help="Install daily cron job")
    group.add_argument("--remove",  action="store_true", help="Remove cron job")
    group.add_argument("--run",     action="store_true", help="Run pipeline once")
    args = parser.parse_args()

    if args.install:
        install_cron()
    elif args.remove:
        remove_cron()
    elif args.run:
        run_once()


if __name__ == "__main__":
    main()
