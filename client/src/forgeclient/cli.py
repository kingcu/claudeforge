"""Command-line interface for forge."""
import logging
import sys
import click

from .config import load_config, set_config_value
from .sync import maybe_auto_sync, do_sync, fetch_daily_stats
from .claude_code import get_local_daily_stats
from .local_cache import get_pending_count, list_pending, process_pending_syncs
from .display import console, render_daily_graph, show_sync_status, show_stale_warning


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr
    )


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable debug logging')
def cli(verbose: bool):
    """Forge - Claude Code usage tracker."""
    setup_logging(verbose)


# === Config commands ===

@cli.group()
def config():
    """Manage configuration."""
    pass


@config.command("show")
def config_show():
    """Show current configuration."""
    cfg = load_config()
    console.print("[bold]Current configuration:[/bold]")
    for key, value in cfg.items():
        if key == "api_key" and value:
            value = value[:8] + "..." if len(value) > 8 else "***"
        console.print(f"  {key}: {value}")


@config.command("set")
@click.argument("key", type=click.Choice(["server-url", "api-key", "hostname"]))
@click.argument("value")
def config_set(key: str, value: str):
    """Set a configuration value."""
    key_map = {
        "server-url": "server_url",
        "api-key": "api_key",
        "hostname": "hostname"
    }
    set_config_value(key_map[key], value)
    console.print(f"[green]Set {key}[/green]")


# === Sync commands ===

@cli.command()
@click.option('--force', is_flag=True, help='Force sync even if recently synced')
@click.option('--retry', is_flag=True, help='Only process pending syncs')
@click.option('--status', is_flag=True, help='Show pending sync status')
def sync(force: bool, retry: bool, status: bool):
    """Sync usage data to server."""
    if status:
        pending = list_pending()
        console.print(f"[bold]Pending syncs:[/bold] {len(pending)}")
        for i, item in enumerate(pending[:5]):
            console.print(f"  {i+1}. Queued at {item['queued_at']}")
        if len(pending) > 5:
            console.print(f"  ... and {len(pending) - 5} more")
        return

    if retry:
        cfg = load_config()
        if not cfg.get("server_url") or not cfg.get("api_key"):
            console.print("[red]Server not configured[/red]")
            return
        success, fail = process_pending_syncs(cfg["server_url"], cfg["api_key"])
        console.print(f"[green]Processed {success} pending syncs[/green]")
        if fail > 0:
            console.print(f"[yellow]{fail} still pending[/yellow]")
        return

    result = maybe_auto_sync(force=force) if not force else do_sync(load_config())
    show_sync_status(result, get_pending_count())


# === Stats commands ===

@cli.command()
@click.option('--days', '-d', default=30, help='Number of days to show')
@click.option('--local', is_flag=True, help='Show local data only (no server)')
def tokens(days: int, local: bool):
    """Show daily token usage graph."""
    config = load_config()

    if local:
        # Local mode: read from stats-cache.json directly
        data = get_local_daily_stats(days)
        render_daily_graph(data, f"Local Usage (last {days} days)")
        return

    # Server mode: sync if needed, then fetch from server
    result = maybe_auto_sync()
    show_sync_status(result, get_pending_count())

    if not config.get("last_sync_success", True):
        show_stale_warning(config)

    data = fetch_daily_stats(days)
    if data is None:
        # Fall back to local
        console.print("[yellow]Using local data (server unavailable)[/yellow]")
        data = get_local_daily_stats(days)

    render_daily_graph(data, f"Usage (last {days} days)")


@cli.command()
def stats():
    """Show overall usage statistics."""
    # Similar pattern: sync, fetch from server, display
    console.print("[dim]Not yet implemented[/dim]")


@cli.command()
def models():
    """Show usage breakdown by model."""
    console.print("[dim]Not yet implemented[/dim]")


@cli.command()
def machines():
    """List all synced machines."""
    console.print("[dim]Not yet implemented[/dim]")


if __name__ == "__main__":
    cli()
