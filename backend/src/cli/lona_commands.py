"""Lona Gateway CLI commands."""

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.services.lona_client import LonaClient

lona_app = typer.Typer(no_args_is_help=True)
console = Console()


async def _register_agent() -> None:
    """Register agent with Lona Gateway."""
    async with LonaClient() as client:
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]Registering agent with Lona Gateway..."),
                console=console,
            ) as progress:
                progress.add_task("register", total=None)
                result = await client.register()

            panel_content = (
                f"[bold green]Registration Successful[/bold green]\n\n"
                f"[cyan]Partner ID:[/cyan]   {result.partner_id}\n"
                f"[cyan]Partner Name:[/cyan] {result.partner_name}\n"
                f"[cyan]Permissions:[/cyan]  {', '.join(result.permissions)}\n"
                f"[cyan]Expires At:[/cyan]   {result.expires_at}\n"
                f"[cyan]Token:[/cyan]        {result.token[:20]}..."
            )
            console.print(Panel(panel_content, title="Lona Registration", border_style="green"))
            console.print(
                f"\n[dim]Save this token to your .env as LONA_AGENT_TOKEN to skip "
                f"re-registration:[/dim]\n[cyan]{result.token}[/cyan]"
            )
        except Exception as e:
            console.print(Panel(f"[red]Registration failed: {e}[/red]", title="Error", border_style="red"))
            raise typer.Exit(1)


async def _list_symbols(global_only: bool, limit: int) -> None:
    """List available market data symbols."""
    async with LonaClient() as client:
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]Fetching symbols from Lona Gateway..."),
                console=console,
            ) as progress:
                progress.add_task("fetch", total=None)
                symbols = await client.list_symbols(is_global=global_only, limit=limit)

            if not symbols:
                console.print("[yellow]No symbols found.[/yellow]")
                return

            table = Table(title="Available Symbols", border_style="cyan")
            table.add_column("ID", style="dim", max_width=12)
            table.add_column("Name", style="bold cyan")
            table.add_column("Exchange", style="yellow")
            table.add_column("Asset Class", style="white")
            table.add_column("Frequencies", style="green")
            table.add_column("Global", justify="center")

            for sym in symbols:
                exchange = sym.type_metadata.exchange if sym.type_metadata else "N/A"
                asset_class = sym.type_metadata.asset_class if sym.type_metadata else "N/A"
                freqs = ", ".join(sym.frequencies) if sym.frequencies else "N/A"
                table.add_row(
                    sym.id[:12],
                    sym.name,
                    exchange or "N/A",
                    asset_class or "N/A",
                    freqs,
                    "[green]Yes[/green]" if sym.is_global else "No",
                )

            console.print(table)
            console.print(f"\n[dim]Showing {len(symbols)} symbols[/dim]")
        except Exception as e:
            console.print(f"[red]Failed to fetch symbols: {e}[/red]")
            raise typer.Exit(1)


async def _download_data(symbol: str, interval: str, start: str, end: str) -> None:
    """Download market data from Binance via Lona."""
    async with LonaClient() as client:
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn(f"[bold cyan]Downloading {symbol} data ({interval}) from Binance..."),
                console=console,
            ) as progress:
                progress.add_task("download", total=None)
                result = await client.download_market_data(
                    symbol=symbol,
                    interval=interval,
                    start_date=start,
                    end_date=end,
                )

            panel_content = (
                f"[bold green]Download & Upload Complete[/bold green]\n\n"
                f"[cyan]Symbol:[/cyan]    {symbol}\n"
                f"[cyan]Interval:[/cyan]  {interval}\n"
                f"[cyan]Period:[/cyan]    {start} -> {end}\n"
                f"[cyan]Symbol ID:[/cyan] {result.id}\n\n"
                f"[dim]Use this ID for backtesting: --data-ids {result.id}[/dim]"
            )
            console.print(Panel(panel_content, title="Market Data", border_style="green"))
        except Exception as e:
            console.print(f"[red]Failed to download data: {e}[/red]")
            raise typer.Exit(1)


@lona_app.command("register")
def register() -> None:
    """Register agent with Lona Gateway."""
    asyncio.run(_register_agent())


@lona_app.command("symbols")
def list_symbols(
    global_only: bool = typer.Option(False, "--global", "-g", help="Show only global symbols"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of symbols to display"),
) -> None:
    """List available market data symbols."""
    asyncio.run(_list_symbols(global_only, limit))


@lona_app.command("download")
def download_data(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., BTCUSDT)"),
    interval: str = typer.Option("1h", "--interval", "-i", help="Data interval (1m, 5m, 1h, 1d)"),
    start: str = typer.Option("2024-01-01", "--start", "-s", help="Start date (YYYY-MM-DD)"),
    end: str = typer.Option("2024-12-01", "--end", "-e", help="End date (YYYY-MM-DD)"),
) -> None:
    """Download market data from Binance and upload to Lona."""
    asyncio.run(_download_data(symbol, interval, start, end))
