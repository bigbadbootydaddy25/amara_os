#!/usr/bin/env python3
"""
Learning Ingestion Supervisor — CLI entry point.

Usage
─────
  # Supervise the default AI Brain location
  python run.py

  # Specify a custom brain directory and output location
  python run.py --brain-dir /Users/user/ai-brain --output-dir ./reports

  # Re-run failed jobs (writes rerun_manifest.json)
  python run.py --rerun-failed

  # Check what would happen without writing quarantine files
  python run.py --dry-run

  # Raise the quality bar for memory promotion
  python run.py --min-quality-score 75

  # Verbose logging
  python run.py --verbose

Exit codes
──────────
  0  Run completed (even if some sessions were quarantined/failed)
  1  Unrecoverable error during the run
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure this file's directory is on sys.path so sibling modules resolve
sys.path.insert(0, str(Path(__file__).parent))

from supervisor import LearningIngestionSupervisor, configure_logging

DEFAULT_BRAIN_DIR = Path("/Users/user/ai-brain")
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "reports"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="learning-ingestion-supervisor",
        description="Quality gate and diagnostic supervisor for the AI Brain ingestion pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--brain-dir",
        type=Path,
        default=DEFAULT_BRAIN_DIR,
        metavar="PATH",
        help=f"Root of the AI Brain directory tree (default: {DEFAULT_BRAIN_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        metavar="PATH",
        help=f"Directory for supervisor reports (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--rerun-failed",
        action="store_true",
        help="Write a rerun_manifest.json for FAILED sessions so upstream agents can re-ingest them",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run all checks and generate reports without writing quarantine files or rerun manifests",
    )
    parser.add_argument(
        "--min-quality-score",
        type=float,
        default=60.0,
        metavar="SCORE",
        help="Minimum quality score (0–100) required for memory promotion (default: 60)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    configure_logging(log_level)

    log = logging.getLogger(__name__)

    if not args.brain_dir.exists():
        log.warning(
            "Brain directory does not exist: %s  "
            "(Supervisor will run with empty collections — create the directory to ingest real data)",
            args.brain_dir,
        )

    if args.min_quality_score < 0 or args.min_quality_score > 100:
        parser.error("--min-quality-score must be between 0 and 100")

    supervisor = LearningIngestionSupervisor(
        brain_dir=args.brain_dir,
        output_dir=args.output_dir,
        min_quality_score=args.min_quality_score,
        dry_run=args.dry_run,
    )

    exit_code = supervisor.run(rerun_failed=args.rerun_failed)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
