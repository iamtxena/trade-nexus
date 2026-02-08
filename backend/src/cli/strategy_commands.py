"""Strategy management CLI commands."""

import asyncio
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.agents.graph import get_strategist_agent
from src.schemas.lona import LonaBacktestRequest, LonaReport, LonaSimulationParameters
from src.services.lona_client import LonaClient

strategy_app = typer.Typer(no_args_is_help=True)
console = Console()


async def _create_strategy(description: str, provider: str | None = None) -> None:
    """Create a strategy from natural language description."""
    async with LonaClient() as client:
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]Creating strategy via AI (this may take ~1-2 min)..."),
                console=console,
            ) as progress:
                progress.add_task("create", total=None)
                result = await client.create_strategy_from_description(
                    description=description, provider=provider
                )

            panel_content = (
                f"[bold green]Strategy Created[/bold green]\n\n"
                f"[cyan]Strategy ID:[/cyan]  {result.strategy_id}\n"
                f"[cyan]Name:[/cyan]         {result.name}\n"
                f"[cyan]Explanation:[/cyan]   {result.explanation[:200]}..."
            )
            console.print(Panel(panel_content, title="New Strategy", border_style="green"))
            console.print(Panel(result.code, title="Generated Code", border_style="cyan"))
        except Exception as e:
            console.print(f"[red]Failed to create strategy: {e}[/red]")
            raise typer.Exit(1)


async def _list_strategies() -> None:
    """List all strategies."""
    async with LonaClient() as client:
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]Fetching strategies..."),
                console=console,
            ) as progress:
                progress.add_task("fetch", total=None)
                strategies = await client.list_strategies()

            if not strategies:
                console.print("[yellow]No strategies found. Create one with:[/yellow]")
                console.print("[cyan]  nexus strategy create 'My strategy description...'[/cyan]")
                return

            table = Table(title="Strategies", border_style="cyan")
            table.add_column("ID", style="dim", max_width=12)
            table.add_column("Name", style="bold cyan")
            table.add_column("Description", style="white", max_width=40)
            table.add_column("Version", style="yellow")
            table.add_column("Created At", style="dim")

            for strat in strategies:
                table.add_row(
                    strat.id[:12],
                    strat.name,
                    (strat.description or "")[:40],
                    strat.version,
                    strat.created_at[:10] if strat.created_at else "N/A",
                )

            console.print(table)
            console.print(f"\n[dim]Total: {len(strategies)} strategies[/dim]")
        except Exception as e:
            console.print(f"[red]Failed to list strategies: {e}[/red]")
            raise typer.Exit(1)


async def _backtest(
    strategy_id: str,
    data_ids: list[str],
    start: str,
    end: str,
    cash: float,
    commission: float,
) -> None:
    """Run backtest on a strategy."""
    async with LonaClient() as client:
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]Submitting backtest..."),
                console=console,
            ) as progress:
                progress.add_task("submit", total=None)
                request = LonaBacktestRequest(
                    strategy_id=strategy_id,
                    data_ids=data_ids,
                    start_date=start,
                    end_date=end,
                    simulation_parameters=LonaSimulationParameters(
                        initial_cash=cash,
                    ),
                )
                result = await client.run_backtest(request)

            console.print(f"[green]Backtest submitted. Report ID: {result.report_id}[/green]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[bold yellow]Waiting for backtest report..."),
                console=console,
            ) as progress:
                progress.add_task("wait", total=None)
                report = await client.wait_for_report(result.report_id)

            _display_report(report)
        except Exception as e:
            console.print(f"[red]Backtest failed: {e}[/red]")
            raise typer.Exit(1)


async def _view_report(report_id: str) -> None:
    """View a backtest report."""
    async with LonaClient() as client:
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]Fetching report..."),
                console=console,
            ) as progress:
                progress.add_task("fetch", total=None)
                report = await client.get_report(report_id)

            _display_report(report)
        except Exception as e:
            console.print(f"[red]Failed to fetch report: {e}[/red]")
            raise typer.Exit(1)


def _display_report(report: LonaReport) -> None:
    """Display a backtest report with rich formatting."""
    status = report.status
    status_color = "green" if status == "COMPLETED" else "red" if status == "FAILED" else "yellow"

    header = (
        f"[bold {status_color}]Status: {status}[/bold {status_color}]\n"
        f"[cyan]Report ID:[/cyan]    {report.id}\n"
        f"[cyan]Strategy ID:[/cyan]  {report.strategy_id}"
    )

    if report.error:
        header += f"\n[red]Error: {report.error}[/red]"

    console.print(Panel(header, title="Backtest Report", border_style=status_color))

    stats = report.total_stats
    if stats:
        table = Table(title="Performance Metrics", border_style="cyan")
        table.add_column("Metric", style="bold white")
        table.add_column("Value", style="cyan", justify="right")

        # Display all stats from total_stats dict
        for key, value in stats.items():
            if isinstance(value, float):
                if "return" in key.lower() or "pnl" in key.lower() or "drawdown" in key.lower():
                    color = "green" if value >= 0 else "red"
                    table.add_row(key.replace("_", " ").title(), f"[{color}]{value:+.4f}[/{color}]")
                elif "ratio" in key.lower():
                    color = "green" if value >= 1 else "yellow" if value >= 0 else "red"
                    table.add_row(key.replace("_", " ").title(), f"[{color}]{value:.4f}[/{color}]")
                else:
                    table.add_row(key.replace("_", " ").title(), f"{value:.4f}")
            elif isinstance(value, int):
                table.add_row(key.replace("_", " ").title(), f"{value}")
            elif isinstance(value, str):
                table.add_row(key.replace("_", " ").title(), value)

        console.print(table)


async def _generate_and_test(asset_classes: list[str], capital: float) -> None:
    """Run the full Strategist Brain pipeline."""
    console.print(
        Panel(
            "[bold cyan]Strategist Brain[/bold cyan]\n"
            f"Asset classes: {', '.join(asset_classes)}\n"
            f"Capital: ${capital:,.0f}",
            title="Starting Full Pipeline",
            border_style="cyan",
        )
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]Running Strategist Brain pipeline..."),
        console=console,
    ) as progress:
        progress.add_task("strategist", total=None)
        agent = get_strategist_agent()
        result = await agent.run(asset_classes=asset_classes, capital=capital)

    if result.get("error"):
        console.print(f"[yellow]Warning: {result['error']}[/yellow]")

    if result.get("market_analysis"):
        console.print(
            Panel(
                result["market_analysis"][:500],
                title="Market Analysis",
                border_style="cyan",
            )
        )

    strategies: list[dict[str, Any]] = result.get("strategies", [])
    if strategies:
        table = Table(title="Ranked Strategies", border_style="cyan")
        table.add_column("Rank", style="bold", justify="center")
        table.add_column("Strategy", style="cyan", max_width=50)
        table.add_column("Score", justify="right", style="bold")

        for i, strat in enumerate(strategies, 1):
            table.add_row(
                f"#{i}",
                strat["description"][:50],
                f"{strat['score']:.4f}",
            )
        console.print(table)

    allocation = result.get("allocation")
    if allocation and isinstance(allocation, dict):
        allocs = allocation.get("allocations", [])
        if allocs:
            alloc_table = Table(title="Portfolio Allocation", border_style="green")
            alloc_table.add_column("Strategy", style="cyan")
            alloc_table.add_column("Asset Class", style="yellow")
            alloc_table.add_column("Capital %", justify="right", style="bold")
            alloc_table.add_column("Amount", justify="right", style="green")

            for a in allocs:
                alloc_table.add_row(
                    a.get("strategy_name", "N/A"),
                    a.get("asset_class", "N/A"),
                    f"{a.get('capital_pct', 0):.1f}%",
                    f"${a.get('capital_amount', 0):,.0f}",
                )
            console.print(alloc_table)

        cash_pct = allocation.get("cash_reserve_pct", 0)
        cash_amt = allocation.get("cash_reserve_amount", 0)
        console.print(f"\n[dim]Cash reserve: {cash_pct:.1f}% (${cash_amt:,.0f})[/dim]")

    console.print(Panel("[bold green]Pipeline Complete[/bold green]", border_style="green"))


@strategy_app.command("create")
def create(
    description: str = typer.Argument(..., help="Natural language strategy description"),
    provider: str = typer.Option(
        None, "--provider", "-p", help="AI provider (xai, openai, anthropic, google)"
    ),
) -> None:
    """Create a strategy from natural language description."""
    asyncio.run(_create_strategy(description, provider=provider))


@strategy_app.command("list")
def list_strategies() -> None:
    """List all strategies."""
    asyncio.run(_list_strategies())


@strategy_app.command("backtest")
def backtest(
    strategy_id: str = typer.Argument(..., help="Strategy ID to backtest"),
    data_ids: str = typer.Argument(..., help="Comma-separated market data IDs"),
    start: str = typer.Option("2024-01-01", "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option("2024-12-01", "--end", "-e", help="End date (YYYY-MM-DD)"),
    cash: float = typer.Option(100000, "--cash", "-c", help="Initial capital"),
    commission: float = typer.Option(0.001, "--commission", help="Commission rate"),
) -> None:
    """Run backtest on a strategy."""
    data_id_list = [d.strip() for d in data_ids.split(",") if d.strip()]
    asyncio.run(_backtest(strategy_id, data_id_list, start, end, cash, commission))


@strategy_app.command("report")
def view_report(
    report_id: str = typer.Argument(..., help="Report ID to view"),
) -> None:
    """View a backtest report."""
    asyncio.run(_view_report(report_id))


@strategy_app.command("generate")
def generate_and_test(
    asset_classes: str = typer.Option(
        "crypto,stocks,forex",
        "--assets",
        "-a",
        help="Comma-separated asset classes to analyze",
    ),
    capital: float = typer.Option(100000.0, "--capital", "-c", help="Capital to allocate"),
) -> None:
    """Run the full Strategist Brain: research, generate, backtest, rank."""
    classes = [c.strip() for c in asset_classes.split(",") if c.strip()]
    asyncio.run(_generate_and_test(classes, capital))
