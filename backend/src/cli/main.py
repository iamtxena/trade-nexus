"""Trade Nexus CLI - Main entry point."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.lona_commands import lona_app
from src.cli.portfolio_commands import portfolio_app
from src.cli.strategy_commands import strategy_app
from src.config import get_settings

app = typer.Typer(
    name="nexus",
    help="Trade Nexus - AI Trading Orchestrator CLI",
    no_args_is_help=True,
)

app.add_typer(lona_app, name="lona", help="Lona Gateway operations")
app.add_typer(strategy_app, name="strategy", help="Strategy management")
app.add_typer(portfolio_app, name="portfolio", help="Portfolio management")

console = Console()


@app.command()
def status() -> None:
    """Show system status and configuration."""
    settings = get_settings()

    console.print(
        Panel(
            "[bold cyan]Trade Nexus[/bold cyan] - AI Trading Orchestrator",
            title="System Status",
            border_style="cyan",
        )
    )

    table = Table(border_style="cyan")
    table.add_column("Component", style="bold white")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    # Lona Gateway
    lona_configured = bool(settings.lona_agent_registration_secret or settings.lona_agent_token)
    lona_status = "[green]Configured[/green]" if lona_configured else "[yellow]Not configured[/yellow]"
    table.add_row("Lona Gateway", lona_status, settings.lona_gateway_url)

    # Agent Registration
    agent_registered = bool(settings.lona_agent_token)
    agent_status = "[green]Registered[/green]" if agent_registered else "[yellow]Not registered[/yellow]"
    table.add_row(
        "Agent Registration",
        agent_status,
        f"{settings.lona_agent_id} ({settings.lona_agent_name})",
    )

    # AI Provider
    ai_configured = bool(settings.xai_api_key)
    ai_status = "[green]Connected[/green]" if ai_configured else "[red]Missing API Key[/red]"
    table.add_row("AI Provider (xAI)", ai_status, "Grok via langchain-xai")

    # LangSmith
    ls_configured = bool(settings.langsmith_api_key)
    ls_status = "[green]Enabled[/green]" if ls_configured and settings.langsmith_tracing else "[yellow]Disabled[/yellow]"
    table.add_row("LangSmith Tracing", ls_status, settings.langsmith_project)

    # Supabase
    sb_configured = bool(settings.supabase_url and settings.supabase_key)
    sb_status = "[green]Connected[/green]" if sb_configured else "[yellow]Not configured[/yellow]"
    table.add_row("Supabase", sb_status, settings.supabase_url or "N/A")

    # Live Engine
    table.add_row("Live Engine", "[cyan]Available[/cyan]", settings.live_engine_url)

    # Portfolio
    table.add_row(
        "Portfolio Config",
        "[green]Set[/green]",
        f"Capital: ${settings.initial_capital:,.0f} | Max Pos: {settings.max_position_pct}% | Max DD: {settings.max_drawdown_pct}%",
    )

    # Server
    table.add_row(
        "API Server",
        "[green]Ready[/green]" if not settings.debug else "[yellow]Debug Mode[/yellow]",
        f"{settings.host}:{settings.port}",
    )

    console.print(table)


@app.command()
def server() -> None:
    """Start the FastAPI server."""
    import uvicorn

    settings = get_settings()
    console.print(
        Panel(
            f"[bold cyan]Starting Trade Nexus API Server[/bold cyan]\n\n"
            f"[cyan]Host:[/cyan]  {settings.host}\n"
            f"[cyan]Port:[/cyan]  {settings.port}\n"
            f"[cyan]Debug:[/cyan] {settings.debug}",
            title="Server",
            border_style="cyan",
        )
    )
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
