"""GraphMem CLI — graph-based long-term memory for Claude Code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt

from graphmem.config import DBBackend, EmbedderProvider, LLMProvider
from graphmem.core import GraphMem, run_async
from graphmem.formatters import (
    format_add_result,
    format_context,
    format_list,
    format_ping,
    format_search_results,
    format_status,
)
from graphmem.utils import get_env_path, get_graphmem_home


def _detect_aws_credentials() -> bool:
    """Check if AWS credentials are available (env vars or ~/.aws/credentials)."""
    import os

    if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
        return True
    if (Path.home() / ".aws" / "credentials").exists():
        return True
    return False


app = typer.Typer(
    name="graphmem",
    help="Graph-based long-term memory for Claude Code.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def init():
    """Interactive setup — pick providers and configure credentials."""
    console.print("\n[bold]GraphMem Setup[/bold]\n")

    # Database backend
    db = Prompt.ask(
        "Graph database backend",
        choices=["kuzu", "neo4j"],
        default="kuzu",
    )

    db_path = str(get_graphmem_home() / "db")
    neo4j_uri = ""
    neo4j_user = ""
    neo4j_password = ""
    if db == "neo4j":
        neo4j_uri = Prompt.ask("Neo4j URI", default="bolt://localhost:7687")
        neo4j_user = Prompt.ask("Neo4j user", default="neo4j")
        neo4j_password = Prompt.ask("Neo4j password")
    else:
        db_path = Prompt.ask("Database path", default=db_path)

    # Embedder
    embedder = Prompt.ask(
        "Embedding provider",
        choices=["openai", "bedrock", "local"],
        default="openai",
    )

    # LLM
    llm = Prompt.ask(
        "LLM provider (for entity extraction)",
        choices=["openai", "anthropic", "bedrock", "ollama"],
        default="openai",
    )

    # Collect API keys as needed
    openai_key = ""
    anthropic_key = ""
    aws_region = ""

    if embedder == "openai" or llm == "openai":
        openai_key = Prompt.ask("OpenAI API key")

    if llm == "anthropic":
        anthropic_key = Prompt.ask("Anthropic API key")

    aws_access_key = ""
    aws_secret_key = ""
    if embedder == "bedrock" or llm == "bedrock":
        aws_region = Prompt.ask("AWS region", default="us-east-1")

        # Check if AWS credentials already exist
        has_aws_creds = _detect_aws_credentials()
        if has_aws_creds:
            console.print(
                "[green]Found existing AWS credentials[/green] "
                "(~/.aws/credentials or environment variables)"
            )
        else:
            console.print(
                "[yellow]No AWS credentials found.[/yellow] "
                "Either run 'aws configure' or enter keys below."
            )
            aws_access_key = Prompt.ask("AWS Access Key ID")
            aws_secret_key = Prompt.ask("AWS Secret Access Key")

    ollama_url = ""
    ollama_model = ""
    if llm == "ollama":
        ollama_url = Prompt.ask("Ollama URL", default="http://localhost:11434")
        ollama_model = Prompt.ask("Ollama model", default="llama3.2")

    local_model = ""
    if embedder == "local":
        local_model = Prompt.ask(
            "Local embedding model", default="all-MiniLM-L6-v2"
        )

    # Write .env file
    env_path = get_env_path()
    lines = [
        f"GRAPHMEM_DB_BACKEND={db}",
        f"GRAPHMEM_DB_PATH={db_path}",
        f"GRAPHMEM_EMBEDDER={embedder}",
        f"GRAPHMEM_LLM={llm}",
    ]

    if neo4j_uri:
        lines.append(f"GRAPHMEM_NEO4J_URI={neo4j_uri}")
        lines.append(f"GRAPHMEM_NEO4J_USER={neo4j_user}")
        lines.append(f"GRAPHMEM_NEO4J_PASSWORD={neo4j_password}")

    if openai_key:
        lines.append(f"OPENAI_API_KEY={openai_key}")

    if anthropic_key:
        lines.append(f"ANTHROPIC_API_KEY={anthropic_key}")

    if aws_region:
        lines.append(f"AWS_REGION={aws_region}")

    if aws_access_key:
        lines.append(f"AWS_ACCESS_KEY_ID={aws_access_key}")
        lines.append(f"AWS_SECRET_ACCESS_KEY={aws_secret_key}")

    if ollama_url:
        lines.append(f"GRAPHMEM_OLLAMA_BASE_URL={ollama_url}")
        lines.append(f"GRAPHMEM_OLLAMA_MODEL={ollama_model}")

    if local_model:
        lines.append(f"GRAPHMEM_LOCAL_EMBED_MODEL={local_model}")

    env_path.write_text("\n".join(lines) + "\n")
    console.print(f"\n[green]Config saved to {env_path}[/green]")
    console.print("Run [bold]graphmem ping[/bold] to test connectivity.")


@app.command()
def ping():
    """Test connectivity to database and AI providers."""
    gm = GraphMem()
    results = run_async(gm.ping())
    console.print("\n[bold]Connectivity Check[/bold]")
    format_ping(results)
    run_async(gm.close())


@app.command()
def add(
    content: str = typer.Argument(..., help="The memory text to store"),
    source: str = typer.Option("cli", "--source", "-s", help="Source label"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Memory group"),
):
    """Add a memory. Graphiti extracts entities and facts automatically."""
    gm = GraphMem()
    result = run_async(gm.add(content, source=source, group_id=group))
    format_add_result(result)
    run_async(gm.close())


@app.command()
def query(
    query_text: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Memory group"),
):
    """Search memories using hybrid search (semantic + keyword + graph)."""
    gm = GraphMem()
    group_ids = [group] if group else None
    results = run_async(gm.query(query_text, num_results=limit, group_ids=group_ids))
    format_search_results(results)
    run_async(gm.close())


@app.command()
def context(
    topic: str = typer.Argument(..., help="Topic to explore"),
    depth: int = typer.Option(2, "--depth", "-d", help="Graph traversal depth"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Memory group"),
):
    """Get expanded context around a topic via graph traversal."""
    gm = GraphMem()
    group_ids = [group] if group else None
    ctx = run_async(gm.context(topic, depth=depth, group_ids=group_ids))
    format_context(ctx)
    run_async(gm.close())


@app.command()
def update(
    content: str = typer.Argument(
        ..., help="New information (supersedes conflicting old facts)"
    ),
    source: str = typer.Option("update", "--source", "-s", help="Source label"),
    group: Optional[str] = typer.Option(None, "--group", "-g", help="Memory group"),
):
    """Add new information that may supersede old facts. Graphiti handles temporal invalidation."""
    gm = GraphMem()
    result = run_async(gm.add(content, source=source, group_id=group))
    format_add_result(result)
    console.print(
        "[dim]Conflicting old facts are automatically marked as invalid.[/dim]"
    )
    run_async(gm.close())


@app.command()
def remove(
    entity_id: str = typer.Argument(..., help="Entity ID to remove"),
):
    """Remove an entity from the graph."""
    gm = GraphMem()
    ok = run_async(gm.remove(entity_id))
    if ok:
        console.print(f"[green]Removed entity {entity_id}[/green]")
    else:
        console.print(f"[red]Failed to remove entity {entity_id}[/red]")
    run_async(gm.close())


@app.command(name="remove-edge")
def remove_edge(
    edge_id: str = typer.Argument(..., help="Fact/edge ID to remove"),
):
    """Remove a fact/edge from the graph."""
    gm = GraphMem()
    ok = run_async(gm.remove_edge(edge_id))
    if ok:
        console.print(f"[green]Removed edge {edge_id}[/green]")
    else:
        console.print(f"[red]Failed to remove edge {edge_id}[/red]")
    run_async(gm.close())


# --- Browsing & Export ---

list_app = typer.Typer(help="List episodes or entities.")
app.add_typer(list_app, name="list")


@list_app.command("episodes")
def list_episodes(
    limit: int = typer.Option(20, "--limit", "-l"),
    group: Optional[str] = typer.Option(None, "--group", "-g"),
):
    """List recent episodes."""
    gm = GraphMem()
    items = run_async(gm.list_episodes(limit=limit, group_id=group))
    format_list(items, "Episodes")
    run_async(gm.close())


@list_app.command("entities")
def list_entities(
    limit: int = typer.Option(20, "--limit", "-l"),
    group: Optional[str] = typer.Option(None, "--group", "-g"),
):
    """List entities in the graph."""
    gm = GraphMem()
    items = run_async(gm.list_entities(limit=limit, group_id=group))
    format_list(items, "Entities")
    run_async(gm.close())


@app.command()
def status():
    """Show graph database statistics and connection info."""
    gm = GraphMem()
    s = run_async(gm.status())
    format_status(s)
    run_async(gm.close())


@app.command()
def export(
    format: str = typer.Option("json", "--format", "-f", help="Output format"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file"),
    group: Optional[str] = typer.Option(None, "--group", "-g"),
):
    """Export the knowledge graph."""
    gm = GraphMem()
    data = run_async(gm.export_graph(group_id=group))
    run_async(gm.close())

    json_str = json.dumps(data, indent=2)

    if output:
        Path(output).write_text(json_str)
        console.print(f"[green]Exported to {output}[/green]")
    else:
        console.print(json_str)


@app.command()
def viz(
    port: int = typer.Option(8765, "--port", "-p", help="Local server port"),
    static: bool = typer.Option(False, "--static", help="Generate HTML file instead of serving"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path for static HTML"),
    group: Optional[str] = typer.Option(None, "--group", "-g"),
    poll_interval: float = typer.Option(3.0, "--poll-interval", help="Seconds between graph updates (live mode)"),
):
    """Open an interactive graph visualization in the browser."""
    import asyncio
    import re
    import webbrowser

    gm = GraphMem()
    data = run_async(gm.viz_data(group_id=group))

    node_count = len(data.get("nodes", []))
    link_count = len(data.get("links", []))

    if node_count == 0:
        console.print("[yellow]No entities to visualize. Add some memories first.[/yellow]")
        run_async(gm.close())
        return

    # Load HTML template and inject data
    template_path = Path(__file__).parent / "viz" / "graph.html"
    template = template_path.read_text()

    graph_json = json.dumps(data)
    html = re.sub(
        r'/\*GRAPH_JSON\*/.*?/\*END_GRAPH_JSON\*/',
        lambda _: graph_json,
        template,
        flags=re.DOTALL,
    )

    if static:
        run_async(gm.close())
        out_path = output or "graphmem-viz.html"
        Path(out_path).write_text(html)
        console.print(f"[green]Saved to {out_path}[/green] ({node_count} entities, {link_count} facts)")
        return

    # Live mode: inject WS port and start live server
    ws_port = port + 1
    html = re.sub(
        r'/\*WS_PORT\*/.*?/\*END_WS_PORT\*/',
        lambda _: str(ws_port),
        html,
        flags=re.DOTALL,
    )

    from graphmem.viz.server import VizServer

    server = VizServer(html, port, gm, poll_interval=poll_interval, group_id=group)

    url = f"http://127.0.0.1:{port}"
    webbrowser.open(url)
    console.print(f"[green]Serving graph at {url}[/green] ({node_count} entities, {link_count} facts)")
    console.print(f"[dim]Live updates on ws://127.0.0.1:{ws_port}, polling every {poll_interval}s. Press Ctrl+C to stop[/dim]")

    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        run_async(gm.close())


@app.command(name="install-command")
def install_command():
    """Install the /memory slash command globally for Claude Code."""
    import importlib.resources

    commands_dir = Path.home() / ".claude" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    dest = commands_dir / "memory.md"

    src = importlib.resources.files("graphmem.commands").joinpath("memory.md")
    dest.write_text(src.read_text())

    console.print(f"[green]Installed /memory command to {dest}[/green]")
    console.print("Use [bold]/memory setup[/bold] in any Claude Code session to configure a project.")


if __name__ == "__main__":
    app()
