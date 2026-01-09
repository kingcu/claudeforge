"""Command-line interface for forge."""
import json
import logging
import sys
from pathlib import Path

import click

from .config import load_config, set_config_value, save_config
from .sync import maybe_auto_sync, do_sync, fetch_daily_stats, test_connection
from .claude_code import get_local_daily_stats, get_local_model_usage, get_local_summary, get_daily_stats_from_sessions
from .local_cache import get_pending_count, list_pending, process_pending_syncs, compute_daily_deltas, get_usage_snapshots
from .display import console, render_daily_graph, render_recent_table, show_sync_status, show_stale_warning, render_model_usage


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


# === Setup command ===

CLAUDE_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
FORGE_HOOK = {
    "type": "command",
    "command": "forge sync 2>/dev/null || true"
}


def is_hook_installed() -> bool:
    """Check if the forge sync hook is already installed."""
    if not CLAUDE_SETTINGS_PATH.exists():
        return False
    try:
        settings = json.loads(CLAUDE_SETTINGS_PATH.read_text())
        hooks = settings.get("hooks", {}).get("UserPromptSubmit", [])
        for matcher in hooks:
            for hook in matcher.get("hooks", []):
                if hook.get("command", "").startswith("forge sync"):
                    return True
    except (json.JSONDecodeError, IOError):
        pass
    return False


def install_hook() -> bool:
    """Install the forge sync hook into Claude settings. Returns success."""
    try:
        # Load existing settings or create new
        if CLAUDE_SETTINGS_PATH.exists():
            settings = json.loads(CLAUDE_SETTINGS_PATH.read_text())
        else:
            settings = {}

        # Ensure hooks structure exists
        if "hooks" not in settings:
            settings["hooks"] = {}
        if "UserPromptSubmit" not in settings["hooks"]:
            settings["hooks"]["UserPromptSubmit"] = []

        # Find or create the catch-all matcher
        matchers = settings["hooks"]["UserPromptSubmit"]
        catch_all = None
        for matcher in matchers:
            if matcher.get("matcher") == "":
                catch_all = matcher
                break

        if catch_all is None:
            catch_all = {"matcher": "", "hooks": []}
            matchers.append(catch_all)

        # Add our hook if not already present
        if "hooks" not in catch_all:
            catch_all["hooks"] = []

        for hook in catch_all["hooks"]:
            if hook.get("command", "").startswith("forge sync"):
                return True  # Already installed

        catch_all["hooks"].append(FORGE_HOOK)

        # Write back
        CLAUDE_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        CLAUDE_SETTINGS_PATH.write_text(json.dumps(settings, indent=2))
        return True
    except Exception:
        return False


@cli.command()
def setup():
    """Interactive setup wizard."""
    console.print("[bold]Forge Setup[/bold]\n")

    config = load_config()

    # Prompt for server URL with existing value as default
    default_url = config.get("server_url") or "http://localhost:8420"
    server_url = click.prompt("Server URL", default=default_url)

    # Prompt for API key, allowing reuse of existing
    existing_key = config.get("api_key")
    if existing_key:
        masked = existing_key[:8] + "..." if len(existing_key) > 8 else "***"
        api_key = click.prompt(
            f"API Key [enter to keep {masked}]",
            default="",
            hide_input=True,
            show_default=False
        )
        if not api_key:
            api_key = existing_key
    else:
        api_key = click.prompt("API Key", hide_input=True)

    # Test connection
    console.print("\nTesting connection...", end=" ")
    success, message = test_connection(server_url, api_key)

    if success:
        console.print("[green]OK[/green]")
        config["server_url"] = server_url
        config["api_key"] = api_key
        save_config(config)
        console.print("[green]Configuration saved![/green]")
    else:
        console.print(f"[red]Failed[/red]")
        console.print(f"[red]{message}[/red]")
        if click.confirm("\nSave anyway?", default=False):
            config["server_url"] = server_url
            config["api_key"] = api_key
            save_config(config)
            console.print("[yellow]Configuration saved (connection not verified)[/yellow]")
        else:
            return  # Don't offer hook installation if config not saved

    # Offer to install Claude hook
    console.print()
    if is_hook_installed():
        console.print("[dim]Auto-sync hook already installed[/dim]")
    elif click.confirm("Install Claude hook for automatic hourly sync?", default=True):
        if install_hook():
            console.print("[green]Hook installed![/green]")
            console.print("[dim]Forge will sync automatically on each Claude prompt (max once per hour)[/dim]")
        else:
            console.print("[red]Failed to install hook[/red]")
            console.print(f"[dim]You can manually add it to {CLAUDE_SETTINGS_PATH}[/dim]")


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
@click.option('--days', '-d', default=30, help='Number of days of history to fetch')
@click.option('--local', is_flag=True, help='Show local data only (no server)')
@click.option('--graph', '-g', is_flag=True, help='Show full graph instead of table')
@click.option('--output-only', is_flag=True, help='Show only output tokens (exclude cache)')
def tokens(days: int, local: bool, graph: bool, output_only: bool):
    """Show daily token usage.

    By default shows a table of the last 7 days with stats.
    Use --graph for a full bar chart of all days.
    """
    config = load_config()

    if local:
        if output_only:
            data = get_local_daily_stats(days)
        else:
            data = get_daily_stats_from_sessions(days)
            if not data:
                console.print("[yellow]No session data found[/yellow]")
                return

        if graph:
            title = f"Local Usage - {'Output Only' if output_only else 'All Tokens'} (last {days} days)"
            render_daily_graph(data, title)
        else:
            render_recent_table(data)
        return

    # Server mode: sync if needed, then fetch from server
    result = maybe_auto_sync()
    show_sync_status(result, get_pending_count())

    if not config.get("last_sync_success", True):
        show_stale_warning(config)

    data = fetch_daily_stats(days)
    if data is None:
        console.print("[yellow]Using local data (server unavailable)[/yellow]")
        if not output_only:
            data = get_daily_stats_from_sessions(days)
        if not data:
            data = get_local_daily_stats(days)

    if graph:
        render_daily_graph(data, f"Usage (last {days} days)")
    else:
        render_recent_table(data)


@cli.command()
@click.option('--local', is_flag=True, help='Show local data only (no server)')
def stats(local: bool):
    """Show detailed token usage breakdown."""
    if local:
        model_usage = get_local_model_usage()
        summary = get_local_summary()
        render_model_usage(model_usage, summary)
        return

    # TODO: fetch from server when implemented
    # For now, just show local data
    model_usage = get_local_model_usage()
    summary = get_local_summary()
    render_model_usage(model_usage, summary)


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
