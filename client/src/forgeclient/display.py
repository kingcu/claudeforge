"""Terminal display using Rich."""
from rich.console import Console

console = Console()

BAR_CHARS = " ▁▂▃▄▅▆▇█"
GRAPH_HEIGHT = 12


def format_number(n: int) -> str:
    """Format number with K/M suffix."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def render_daily_graph(data: list[dict], title: str):
    """Render a vertical bar chart with Y-axis labels."""
    if not data:
        console.print("[yellow]No usage data available[/yellow]")
        return

    totals = [d.get("total_tokens", 0) for d in data]
    max_val = max(totals) if totals else 1

    lines = []
    lines.append("")
    lines.append(f"  [bold cyan]{title}[/bold cyan]")
    lines.append(f"  [dim]{'─' * 50}[/dim]")

    # Build vertical bar chart
    for row in range(GRAPH_HEIGHT, 0, -1):
        threshold = (row / GRAPH_HEIGHT) * max_val

        # Y-axis label
        if row == GRAPH_HEIGHT:
            label = format_number(int(max_val)).rjust(6)
        elif row == GRAPH_HEIGHT // 2:
            label = format_number(int(max_val / 2)).rjust(6)
        elif row == 1:
            label = "0".rjust(6)
        else:
            label = " " * 6

        line = f"[dim]{label}[/dim] │"

        for total in totals:
            if total >= threshold:
                line += "[green]█[/green]"
            elif total >= threshold - (max_val / GRAPH_HEIGHT):
                idx = int((total % (max_val / GRAPH_HEIGHT)) / (max_val / GRAPH_HEIGHT) * 8)
                line += f"[green]{BAR_CHARS[idx]}[/green]"
            else:
                line += " "

        lines.append(line)

    # X-axis with tick marks
    num_days = len(totals)
    lines.append(f"       └{'─' * num_days}")

    # Date labels - show first, middle, last for orientation
    if data:
        first = data[0]["date"][5:]  # MM-DD
        last = data[-1]["date"][5:]

        if num_days >= 20:
            # Show first, middle, last
            mid_idx = num_days // 2
            mid = data[mid_idx]["date"][5:]
            lines.append(f"[dim]        {first}{'─' * (mid_idx - 3)}┬{'─' * (num_days - mid_idx - 3)}{last}[/dim]")
            lines.append(f"[dim]        {' ' * (mid_idx - 2)}{mid}[/dim]")
        elif num_days >= 10:
            lines.append(f"[dim]        {first} {'─' * (num_days - 10)} {last}[/dim]")
        else:
            lines.append(f"[dim]        {first} → {last}[/dim]")

        # Show the peak day
        max_tokens = max(totals)
        peak_idx = totals.index(max_tokens)
        peak_date = data[peak_idx]["date"]
        lines.append(f"[dim]        Peak: {peak_date} ({format_number(max_tokens)} tokens)[/dim]")

    lines.append("")

    # Summary stats
    total_tokens = sum(totals)
    total_messages = sum(d.get("message_count", 0) for d in data)
    lines.append(f"  [dim]{'─' * 50}[/dim]")
    lines.append(f"  [bold]Total:[/bold] {format_number(total_tokens)} tokens, {total_messages:,} messages")
    if len(data) > 0:
        lines.append(f"  [bold]Average:[/bold] {format_number(total_tokens // len(data))}/day")
    lines.append("")

    console.print("\n".join(lines))


def show_sync_status(result, pending_count: int = 0):
    """Show sync status with appropriate styling."""
    if result.status == "success":
        msg = f"[green]✓ Synced {result.records_synced} records[/green]"
    elif result.status == "queued":
        msg = f"[yellow]⚠ {result.message} (queued for retry)[/yellow]"
    elif result.status == "skipped":
        msg = f"[dim]↷ {result.message}[/dim]"
    else:
        msg = f"[red]✗ {result.message}[/red]"

    if pending_count > 0:
        msg += f" [dim]({pending_count} pending)[/dim]"

    console.print(msg)


def show_stale_warning(config: dict):
    """Warn if data might be stale."""
    if not config.get("last_sync_success", True):
        last_error = config.get("last_error", "unknown error")
        console.print(f"[yellow]⚠ Last sync failed: {last_error}[/yellow]")
        console.print("[dim]  Showing cached data. Run 'forge sync' to retry.[/dim]")
