"""Rich output formatting for CLI display."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

console = Console()


def format_add_result(result: dict[str, Any]) -> None:
    """Display the result of adding a memory."""
    console.print(f"\n[green]Episode created:[/green] {result['episode_id']}")

    if result["entities"]:
        table = Table(title="Extracted Entities")
        table.add_column("ID", style="dim", max_width=12)
        table.add_column("Name", style="cyan")
        table.add_column("Summary", style="white")
        for entity in result["entities"]:
            table.add_row(
                entity["id"][:12] + "...",
                entity["name"],
                (entity.get("summary") or "")[:80],
            )
        console.print(table)

    if result["facts"]:
        table = Table(title="Extracted Facts")
        table.add_column("ID", style="dim", max_width=12)
        table.add_column("Fact", style="white")
        for fact in result["facts"]:
            table.add_row(
                fact["id"][:12] + "...",
                fact.get("fact", fact.get("source", "")),
            )
        console.print(table)

    if not result["entities"] and not result["facts"]:
        console.print("[yellow]No entities or facts extracted.[/yellow]")


def format_search_results(results: list[dict[str, Any]]) -> None:
    """Display search results."""
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    table = Table(title="Search Results")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Fact", style="white")
    table.add_column("Valid", style="green", max_width=12)
    table.add_column("Invalid", style="red", max_width=12)

    for r in results:
        valid = _format_date(r.get("valid_at"))
        invalid = _format_date(r.get("invalid_at"))
        table.add_row(
            r["id"][:12] + "...",
            r.get("fact") or r.get("name", ""),
            valid,
            invalid or "-",
        )

    console.print(table)


def format_context(ctx: dict[str, Any]) -> None:
    """Display expanded graph context as a tree."""
    tree = Tree("[bold]Context Graph[/bold]")

    if ctx.get("entities"):
        entities_branch = tree.add("[cyan]Entities[/cyan]")
        for e in ctx["entities"]:
            entities_branch.add(
                f"[bold]{e['name']}[/bold] — {(e.get('summary') or '')[:60]}"
            )

    if ctx.get("facts"):
        facts_branch = tree.add("[green]Facts[/green]")
        for f in ctx["facts"]:
            status = "[red](invalid)[/red]" if f.get("invalid_at") else "[green](valid)[/green]"
            facts_branch.add(f"{f.get('fact', f.get('name', ''))} {status}")

    if ctx.get("communities"):
        comm_branch = tree.add("[magenta]Communities[/magenta]")
        for c in ctx["communities"]:
            comm_branch.add(
                f"[bold]{c['name']}[/bold] — {(c.get('summary') or '')[:60]}"
            )

    if ctx.get("episodes"):
        ep_branch = tree.add("[blue]Episodes[/blue]")
        for ep in ctx["episodes"]:
            ep_branch.add(f"{ep['name']} — {(ep.get('content') or '')[:60]}")

    console.print(tree)


def format_list(items: list[dict[str, Any]], title: str) -> None:
    """Display a list of items as a table."""
    if not items:
        console.print(f"[yellow]No {title.lower()} found.[/yellow]")
        return

    table = Table(title=title)
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Name", style="cyan")
    table.add_column("Details", style="white")
    table.add_column("Created", style="dim", max_width=20)

    for item in items:
        detail = item.get("summary") or item.get("content") or ""
        table.add_row(
            item["id"][:12] + "...",
            item.get("name", ""),
            detail[:80],
            _format_date(item.get("created_at")) or "",
        )

    console.print(table)


def format_status(status: dict[str, Any]) -> None:
    """Display graph status."""
    panel_content = ""
    if status.get("connected"):
        panel_content += f"[green]Connected[/green]\n"
        panel_content += f"Backend:  {status.get('db_backend', 'unknown')}\n"
        panel_content += f"Path:     {status.get('db_path', 'unknown')}\n"
        panel_content += f"Embedder: {status.get('embedder', 'unknown')}\n"
        panel_content += f"LLM:      {status.get('llm', 'unknown')}\n"
        panel_content += f"Entities: {status.get('entity_count', 0)}\n"
        panel_content += f"Episodes: {status.get('episode_count', 0)}"
    else:
        panel_content += f"[red]Disconnected[/red]\n"
        panel_content += f"Error: {status.get('error', 'unknown')}"

    console.print(Panel(panel_content, title="GraphMem Status"))


def format_ping(results: dict[str, bool]) -> None:
    """Display ping results."""
    for service, ok in results.items():
        status = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
        console.print(f"  {service}: {status}")


def _format_date(date_str: str | None) -> str | None:
    """Format a date string for display."""
    if not date_str or date_str == "None":
        return None
    try:
        return date_str[:10]
    except (IndexError, TypeError):
        return None
