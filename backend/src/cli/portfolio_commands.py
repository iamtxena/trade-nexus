"""Portfolio management CLI commands."""

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.agents.graph import get_strategist_agent
from src.config import get_settings

portfolio_app = typer.Typer(no_args_is_help=True)
console = Console()


async def _plan(capital: float, asset_classes: list[str]) -> None:
    """Generate portfolio plan using the Strategist Brain."""
    settings = get_settings()
    console.print(
        Panel(
            f"[bold cyan]Portfolio Planning[/bold cyan]\n\n"
            f"[cyan]Capital:[/cyan]      ${capital:,.2f}\n"
            f"[cyan]Assets:[/cyan]       {', '.join(asset_classes)}\n"
            f"[cyan]Max Position:[/cyan] {settings.max_position_pct}%\n"
            f"[cyan]Max Drawdown:[/cyan] {settings.max_drawdown_pct}%",
            title="Configuration",
            border_style="cyan",
        )
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]Running Strategist Brain for portfolio allocation..."),
        console=console,
    ) as progress:
        progress.add_task("plan", total=None)
        agent = get_strategist_agent()
        result = await agent.run(asset_classes=asset_classes, capital=capital)

    if result.get("error"):
        console.print(f"[yellow]Warning: {result['error']}[/yellow]")

    # Display market analysis summary
    if result.get("market_analysis"):
        console.print(
            Panel(
                result["market_analysis"][:300] + "...",
                title="Market Analysis",
                border_style="dim cyan",
            )
        )

    # Display ranked strategies
    strategies = result.get("strategies", [])
    if strategies:
        strat_table = Table(title="Ranked Strategies", border_style="cyan")
        strat_table.add_column("Rank", style="bold", justify="center")
        strat_table.add_column("Strategy", style="cyan", max_width=50)
        strat_table.add_column("Score", justify="right")

        for i, s in enumerate(strategies, 1):
            score = s.get("score", 0)
            color = "green" if score > 0.5 else "yellow" if score > 0.3 else "red"
            strat_table.add_row(f"#{i}", s["description"][:50], f"[{color}]{score:.4f}[/{color}]")
        console.print(strat_table)

    # Display allocation
    allocation = result.get("allocation")
    if allocation and isinstance(allocation, dict):
        allocs = allocation.get("allocations", [])
        if allocs:
            alloc_table = Table(title="Portfolio Allocation", border_style="green")
            alloc_table.add_column("Strategy", style="cyan")
            alloc_table.add_column("Asset Class", style="yellow")
            alloc_table.add_column("Capital %", justify="right", style="bold")
            alloc_table.add_column("Amount", justify="right", style="green")
            alloc_table.add_column("Rationale", style="dim", max_width=35)

            for a in allocs:
                alloc_table.add_row(
                    a.get("strategy_name", "N/A"),
                    a.get("asset_class", "N/A"),
                    f"{a.get('capital_pct', 0):.1f}%",
                    f"${a.get('capital_amount', 0):,.0f}",
                    a.get("rationale", "")[:35],
                )
            console.print(alloc_table)

        cash_pct = allocation.get("cash_reserve_pct", 0)
        cash_amt = allocation.get("cash_reserve_amount", 0)
        console.print(f"\n[dim]Cash reserve: {cash_pct:.1f}% (${cash_amt:,.0f})[/dim]")

        risk = allocation.get("risk_assessment")
        if risk:
            console.print(Panel(risk[:200], title="Risk Assessment", border_style="yellow"))

    console.print(f"\n[bold]Total Capital:[/bold] [green]${capital:,.2f}[/green]")


async def _status() -> None:
    """Show current portfolio status."""
    settings = get_settings()

    console.print(
        Panel(
            "[bold cyan]Portfolio Status[/bold cyan]",
            title="Trade Nexus Portfolio",
            border_style="cyan",
        )
    )

    summary_table = Table(title="Portfolio Summary", border_style="cyan")
    summary_table.add_column("Metric", style="bold white")
    summary_table.add_column("Value", style="cyan", justify="right")

    summary_table.add_row("Initial Capital", f"${settings.initial_capital:,.2f}")
    summary_table.add_row("Max Position Size", f"{settings.max_position_pct}%")
    summary_table.add_row("Max Drawdown Limit", f"{settings.max_drawdown_pct}%")
    summary_table.add_row("Live Engine", settings.live_engine_url)

    console.print(summary_table)
    console.print(
        "\n[yellow]Live portfolio tracking will be available once live-engine "
        "integration is complete (Phase 2).[/yellow]"
    )


async def _paper_start(capital: float) -> None:
    """Start paper trading session (placeholder for Phase 2)."""
    settings = get_settings()

    console.print(
        Panel(
            f"[bold yellow]Paper Trading Mode[/bold yellow]\n\n"
            f"[cyan]Capital:[/cyan]       ${capital:,.2f}\n"
            f"[cyan]Max Position:[/cyan]  {settings.max_position_pct}%\n"
            f"[cyan]Max Drawdown:[/cyan]  {settings.max_drawdown_pct}%\n"
            f"[cyan]Live Engine:[/cyan]   {settings.live_engine_url}",
            title="Paper Trading Configuration",
            border_style="yellow",
        )
    )

    console.print(
        "[yellow]Paper trading requires live-engine integration (Phase 2).[/yellow]\n"
        "[dim]Use 'nexus strategy generate' to research and generate strategies first,[/dim]\n"
        "[dim]then 'nexus portfolio plan' to create a portfolio allocation.[/dim]"
    )


@portfolio_app.command("plan")
def plan(
    capital: float = typer.Option(100000.0, "--capital", "-c", help="Total capital to allocate"),
    asset_classes: str = typer.Option(
        "crypto,stocks,forex",
        "--assets",
        "-a",
        help="Comma-separated asset classes",
    ),
) -> None:
    """Generate portfolio plan using the Strategist Brain."""
    classes = [c.strip() for c in asset_classes.split(",") if c.strip()]
    asyncio.run(_plan(capital, classes))


@portfolio_app.command("status")
def status() -> None:
    """Show current portfolio status."""
    asyncio.run(_status())


@portfolio_app.command("paper-start")
def paper_start(
    capital: float = typer.Option(100000.0, "--capital", "-c", help="Starting capital for paper trading"),
) -> None:
    """Start paper trading with the planned portfolio (Phase 2)."""
    asyncio.run(_paper_start(capital))
