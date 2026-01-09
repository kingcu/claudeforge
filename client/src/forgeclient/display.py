"""Terminal display using Rich."""
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table

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


def _calculate_streak(data: list[dict]) -> int:
    """Calculate consecutive days of usage ending today or yesterday."""
    if not data:
        return 0

    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    dates_with_usage = {d["date"] for d in data if d.get("total_tokens", 0) > 0}

    # Start counting from today or yesterday
    if today in dates_with_usage:
        start = datetime.now()
    elif yesterday in dates_with_usage:
        start = datetime.now() - timedelta(days=1)
    else:
        return 0

    streak = 0
    current = start
    while current.strftime('%Y-%m-%d') in dates_with_usage:
        streak += 1
        current -= timedelta(days=1)

    return streak


def _mini_sparkline(values: list[int], width: int = 7) -> str:
    """Create a mini sparkline from values."""
    if not values:
        return ""
    max_val = max(values) if max(values) > 0 else 1
    return "".join(BAR_CHARS[min(8, int(v / max_val * 8))] for v in values[-width:])


def render_recent_table(data: list[dict], days: int = 7):
    """Render a table of recent daily usage with stats."""
    if not data:
        console.print("[yellow]No usage data available[/yellow]")
        return

    # Calculate 30-day average
    avg_30d = sum(d.get("total_tokens", 0) for d in data) / len(data) if data else 0

    # Get last N days
    recent = data[-days:] if len(data) >= days else data

    # Calculate streak
    streak = _calculate_streak(data)

    # Build table
    table = Table(title="Recent Usage", show_header=True, header_style="bold cyan")
    table.add_column("Date", style="dim")
    table.add_column("Day", style="dim")
    table.add_column("Tokens", justify="right")
    table.add_column("vs Avg", justify="right")
    table.add_column("Trend", justify="center")
    table.add_column("Spark", justify="left")

    prev_total = None
    totals = [d.get("total_tokens", 0) for d in recent]

    for i, day in enumerate(recent):
        date_str = day["date"]
        total = day.get("total_tokens", 0)

        # Day of week
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            dow = dt.strftime('%a')
        except ValueError:
            dow = "?"

        # Format tokens
        tokens_str = format_number(total)

        # Percentage of average
        if avg_30d > 0:
            pct = (total / avg_30d) * 100
            if pct >= 150:
                pct_str = f"[bold green]{pct:.0f}%[/bold green]"
            elif pct >= 80:
                pct_str = f"[green]{pct:.0f}%[/green]"
            elif pct >= 50:
                pct_str = f"[yellow]{pct:.0f}%[/yellow]"
            else:
                pct_str = f"[dim]{pct:.0f}%[/dim]"
        else:
            pct_str = "-"

        # Trend vs previous day
        if prev_total is not None and prev_total > 0:
            change = ((total - prev_total) / prev_total) * 100
            if change > 20:
                trend = "[green]↑[/green]"
            elif change < -20:
                trend = "[red]↓[/red]"
            else:
                trend = "[dim]→[/dim]"
        else:
            trend = ""

        # Mini sparkline showing position in week
        spark = _mini_sparkline(totals[:i+1])

        table.add_row(date_str[5:], dow, tokens_str, pct_str, trend, f"[green]{spark}[/green]")
        prev_total = total

    console.print()
    console.print(table)

    # Summary line
    total_recent = sum(totals)
    console.print()
    console.print(f"  [bold]Week total:[/bold] {format_number(total_recent)}  │  [bold]30d avg:[/bold] {format_number(int(avg_30d))}/day  │  [bold]Streak:[/bold] {streak} day{'s' if streak != 1 else ''} {'🔥' if streak >= 7 else ''}")
    console.print()


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


def render_model_usage(model_usage: list[dict], summary: dict = None):
    """Render detailed model usage breakdown."""
    if not model_usage:
        console.print("[yellow]No usage data available[/yellow]")
        return

    lines = []
    lines.append("")
    lines.append("  [bold cyan]Token Usage by Model[/bold cyan]")
    lines.append(f"  [dim]{'─' * 60}[/dim]")

    grand_total = 0
    grand_input = 0
    grand_output = 0
    grand_cache_read = 0
    grand_cache_create = 0

    for usage in sorted(model_usage, key=lambda x: x.get("input_tokens", 0) + x.get("output_tokens", 0), reverse=True):
        model = usage.get("model", "unknown")
        input_tok = usage.get("input_tokens", 0)
        output_tok = usage.get("output_tokens", 0)
        cache_read = usage.get("cache_read_tokens", 0)
        cache_create = usage.get("cache_creation_tokens", 0)

        # Shorten model name for display
        short_model = model.replace("claude-", "").replace("-20251101", "")

        lines.append(f"")
        lines.append(f"  [bold]{short_model}[/bold]")
        lines.append(f"    Input:          {format_number(input_tok):>10}")
        lines.append(f"    Output:         {format_number(output_tok):>10}")
        lines.append(f"    Cache read:     {format_number(cache_read):>10}")
        lines.append(f"    Cache create:   {format_number(cache_create):>10}")

        subtotal = input_tok + output_tok
        lines.append(f"    [dim]Subtotal:       {format_number(subtotal):>10}[/dim]")

        grand_input += input_tok
        grand_output += output_tok
        grand_cache_read += cache_read
        grand_cache_create += cache_create
        grand_total += subtotal

    lines.append("")
    lines.append(f"  [dim]{'─' * 60}[/dim]")
    lines.append(f"  [bold]Totals (all models)[/bold]")
    lines.append(f"    Input:          {format_number(grand_input):>10}")
    lines.append(f"    Output:         {format_number(grand_output):>10}")
    lines.append(f"    Cache read:     {format_number(grand_cache_read):>10}  [dim](not billed)[/dim]")
    lines.append(f"    Cache create:   {format_number(grand_cache_create):>10}")
    lines.append(f"    [bold]Total:          {format_number(grand_total):>10}[/bold]  [dim](input + output)[/dim]")

    # Include cache in "all tokens" total
    all_tokens = grand_input + grand_output + grand_cache_read + grand_cache_create
    lines.append(f"    [dim]All tokens:     {format_number(all_tokens):>10}  (including cache)[/dim]")

    if summary:
        lines.append("")
        lines.append(f"  [dim]{'─' * 60}[/dim]")
        if summary.get("total_messages"):
            lines.append(f"  Messages: {summary['total_messages']:,}")
        if summary.get("total_sessions"):
            lines.append(f"  Sessions: {summary['total_sessions']:,}")
        if summary.get("first_session_date"):
            lines.append(f"  Since: {summary['first_session_date']}")

    lines.append("")
    console.print("\n".join(lines))
