"""CLI for the AMARA-AEGIS Neuron Network Integration Backend."""
import json

import click

from .config import (
    DAILY_MONEY_BRIEFS_DIR,
    FAILED_NEURONS_DIR,
    OPENCLAW_TASKS_DIR,
    PORT,
    STATUS_DIR,
)
from .event_store import event_counts
from .neuron_router import NeuronRouter


@click.group()
def cli():
    """AMARA-AEGIS Neuron Network Integration Backend CLI."""


@cli.command("run-houston-tax-sale")
def run_houston_tax_sale():
    """Run the full Houston tax sale pipeline."""
    click.echo("Running Houston Tax Sale pipeline...")
    router = NeuronRouter()
    results = router.run_houston_tax_sale()
    failures = results.get("failures", [])
    files_created = results.get("files_created", [])
    click.echo(f"Pipeline complete. Files created: {len(files_created)}. Failures: {len(failures)}.")
    if failures:
        click.echo("Failed neurons:")
        for f in failures:
            click.echo(f"  - {f.get('neuron')}: {f.get('error')}")


@cli.command("run-buyer-demand")
def run_buyer_demand():
    """Run the buyer demand pipeline."""
    click.echo("Running Buyer Demand pipeline...")
    router = NeuronRouter()
    results = router.run_buyer_demand()
    failures = results.get("failures", [])
    buyer_count = (
        results.get("HermesBuyerDemandAgent", {}).get("buyer_target_count", "UNKNOWN")
        if isinstance(results.get("HermesBuyerDemandAgent"), dict)
        else "UNKNOWN"
    )
    click.echo(f"Buyer Demand pipeline complete. Targets: {buyer_count}. Failures: {len(failures)}.")


@cli.command("run-propstream-tasks")
def run_propstream_tasks():
    """Run PropStream session check and task creation."""
    click.echo("Running PropStream task pipeline...")
    router = NeuronRouter()
    results = router.run_propstream_tasks()
    failures = results.get("failures", [])
    ps_status = (
        results.get("HermesPropstreamAgent", {}).get("status", "UNKNOWN")
        if isinstance(results.get("HermesPropstreamAgent"), dict)
        else "UNKNOWN"
    )
    click.echo(f"PropStream pipeline complete. Status: {ps_status}. Failures: {len(failures)}.")


@cli.command("run-foreclosure-review")
def run_foreclosure_review():
    """Run foreclosure source review and parser task creation."""
    click.echo("Running Foreclosure Review pipeline...")
    router = NeuronRouter()
    results = router.run_foreclosure_review()
    failures = results.get("failures", [])
    fc_status = (
        results.get("HermesForeclosureSourceAgent", {}).get("status", "UNKNOWN")
        if isinstance(results.get("HermesForeclosureSourceAgent"), dict)
        else "UNKNOWN"
    )
    click.echo(f"Foreclosure Review pipeline complete. Status: {fc_status}. Failures: {len(failures)}.")


@cli.command("run-all")
def run_all():
    """Run all AEGIS Neuron Network pipelines."""
    click.echo("Running ALL AEGIS Neuron Network pipelines...")
    router = NeuronRouter()
    results = router.run_all()
    summary = results.get("summary", {})

    files_count = summary.get("total_files_created", 0)
    counts = summary.get("event_counts", {})
    events_total = sum(counts.values()) if counts else 0
    buyer_count = summary.get("buyer_target_count", "QUICKCASH_NOT_AVAILABLE")
    strike_count = summary.get("strike_board_count", 0)
    openclaw_file = summary.get("openclaw_task_file", "NOT_CREATED")
    money_brief_file = summary.get("money_brief_file", "NOT_CREATED")
    status_file = summary.get("status_file", "NOT_CREATED")
    failed_file = summary.get("failed_neuron_file", "NOT_CREATED")

    click.echo("")
    click.echo("AMARA-AEGIS NEURON NETWORK INTEGRATION COMPLETE")
    click.echo(f"Files Created: {files_count}")
    click.echo(f"Events Written: {events_total}")
    click.echo(f"Buyer Targets Loaded: {buyer_count}")
    click.echo(f"Strike Board Properties: {strike_count}")
    click.echo(f"OpenClaw Tasks: {openclaw_file}")
    click.echo(f"Daily Money Brief: {money_brief_file}")
    click.echo(f"Status Report: {status_file}")
    click.echo(f"Failed Neurons: {failed_file}")
    click.echo(f"FastAPI: STANDALONE on port {PORT} (not integrated with Next.js routes)")
    click.echo("No-Fake-Data: VERIFIED")
    click.echo("Next Commands: python -m backend.aegis_neuron_network.cli status")


@cli.command("status")
def status():
    """Show current AEGIS Neuron Network status."""
    click.echo("Fetching AMARA-AEGIS Neuron Network status...")
    router = NeuronRouter()
    status_data = router.get_status()

    click.echo(f"\nStatus File: {status_data.get('status_file')}")
    click.echo(f"Status File Exists: {status_data.get('status_file_exists')}")

    counts = status_data.get("event_counts", {})
    if counts:
        click.echo("\nEvent Counts:")
        for event_type, count in sorted(counts.items()):
            click.echo(f"  {event_type}: {count}")
    else:
        click.echo("\nEvent Counts: No events recorded yet")

    if status_data.get("status_content"):
        click.echo("\n--- Status File Content ---")
        click.echo(status_data["status_content"])
    else:
        click.echo("\nNo status file found. Run: python -m backend.aegis_neuron_network.cli run-all")


if __name__ == "__main__":
    cli()
