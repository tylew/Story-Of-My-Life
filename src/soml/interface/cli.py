"""
Story of My Life CLI - Command-line interface.

Commands:
- soml add "note content" → Add new content
- soml ask "question" → Query the knowledge graph
- soml people → List people
- soml projects → List projects
- soml goals → List goals
- soml timeline → Show recent timeline
- soml open-loops → Show things needing attention
"""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich.panel import Panel

from soml.core.config import settings, setup_logging
from soml.crew.crew import SOMLCrew, get_crew

app = typer.Typer(
    name="soml",
    help="Story of My Life - Personal temporal knowledge graph",
    no_args_is_help=True,
)
console = Console()


def run_async(coro):
    """Run an async function synchronously."""
    return asyncio.run(coro)


def get_crew_instance() -> SOMLCrew:
    """Get or create the global crew instance."""
    return get_crew()


@app.command()
def add(
    content: str = typer.Argument(..., help="The content to add"),
):
    """Add new content to your knowledge graph."""
    setup_logging()
    
    with console.status("Processing..."):
        crew = get_crew_instance()
        result = crew.ingest(content)
    
    if result.success:
        console.print(Panel(
            f"[green]✓ Added to knowledge graph[/green]\n\n{result.message}",
            title="Success",
        ))
        
        # Show what was extracted
        if result.entities:
            console.print("\n[bold]Entities extracted:[/bold]")
            for entity in result.entities:
                console.print(f"  • {entity.get('name', 'Unknown')} ({entity.get('type', 'unknown')})")
        
        if result.relationships:
            console.print("\n[bold]Relationships:[/bold]")
            for rel in result.relationships:
                console.print(f"  • {rel.get('type', 'related')}")
    else:
        console.print(f"[red]Error: {result.message}[/red]")


@app.command()
def ask(
    query: str = typer.Argument(..., help="Your question"),
):
    """Ask a question about your knowledge graph."""
    setup_logging()
    
    with console.status("Searching..."):
        crew = get_crew_instance()
        result = crew.query(query)
    
    if result.success and result.answer:
        console.print(Panel(
            Markdown(result.answer),
            title="Answer",
        ))
        
        if result.sources:
            console.print(f"\n[dim]Based on {len(result.sources)} sources[/dim]")
    else:
        console.print(f"[red]Error: {result.answer or 'No answer'}[/red]")


@app.command()
def people(
    name: Optional[str] = typer.Argument(None, help="Person name to look up"),
):
    """List or look up people."""
    setup_logging()
    
    if name:
        # Look up specific person
        crew = get_crew_instance()
        result = crew.query(f"Tell me about {name}")
        if result.success:
            console.print(Panel(
                Markdown(result.answer or "Person not found"),
                title=name,
            ))
    else:
        # List all people
        from soml.storage.registry import RegistryStore
        from soml.core.types import EntityType
        
        registry = RegistryStore()
        people_list = registry.list_by_type(EntityType.PERSON)
        
        if people_list:
            table = Table(title="People")
            table.add_column("Name", style="cyan")
            table.add_column("Context", style="dim")
            table.add_column("Last Interaction", style="green")
            
            for person in people_list:
                table.add_row(
                    person.get("name", "Unknown"),
                    person.get("disambiguator", "-"),
                    person.get("last_interaction", "-"),
                )
            
            console.print(table)
        else:
            console.print("[dim]No people found[/dim]")


@app.command()
def projects():
    """List active projects."""
    setup_logging()
    
    from soml.storage.registry import RegistryStore
    from soml.core.types import EntityType
    
    registry = RegistryStore()
    project_list = registry.list_by_type(EntityType.PROJECT)
    
    if project_list:
        table = Table(title="Active Projects")
        table.add_column("Name", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Created", style="dim")
        
        for project in project_list:
            table.add_row(
                project.get("name", "Unknown"),
                project.get("status", "-"),
                project.get("created_at", "-")[:10] if project.get("created_at") else "-",
            )
        
        console.print(table)
    else:
        console.print("[dim]No active projects[/dim]")


@app.command()
def goals():
    """List active goals."""
    setup_logging()
    
    from soml.storage.registry import RegistryStore
    from soml.core.types import EntityType
    
    registry = RegistryStore()
    goal_list = registry.list_by_type(EntityType.GOAL)
    
    if goal_list:
        table = Table(title="Active Goals")
        table.add_column("Title", style="cyan")
        table.add_column("Progress", style="green")
        table.add_column("Target Date", style="dim")
        
        for goal in goal_list:
            progress = goal.get("progress", 0)
            table.add_row(
                goal.get("title") or goal.get("name", "Unknown"),
                f"{progress}%",
                goal.get("target_date", "-"),
            )
        
        console.print(table)
    else:
        console.print("[dim]No active goals[/dim]")


@app.command()
def timeline(
    days: int = typer.Option(7, help="Number of days to show"),
):
    """Show recent timeline."""
    setup_logging()
    
    from datetime import datetime, timedelta
    from soml.mcp import tools as mcp_tools
    
    start_date = (datetime.now() - timedelta(days=days)).isoformat()
    end_date = datetime.now().isoformat()
    
    result = mcp_tools.get_timeline(
        start_date=start_date,
        end_date=end_date,
    )
    
    if result:
        table = Table(title=f"Timeline (last {days} days)")
        table.add_column("Date", style="dim")
        table.add_column("Type", style="cyan")
        table.add_column("Description", style="white")
        
        for item in result[:20]:  # Limit display
            table.add_row(
                item.get("date", "")[:10] if item.get("date") else "-",
                item.get("type", "-"),
                item.get("name", "-"),
            )
        
        console.print(table)
        
        if len(result) > 20:
            console.print(f"[dim]...and {len(result) - 20} more[/dim]")
    else:
        console.print("[dim]No recent activity[/dim]")


@app.command("open-loops")
def open_loops():
    """Show things needing attention."""
    setup_logging()
    
    from soml.mcp import tools as mcp_tools
    
    loops = mcp_tools.detect_open_loops()
    
    if loops:
        table = Table(title="Open Loops")
        table.add_column("Type", style="cyan")
        table.add_column("Prompt", style="white")
        table.add_column("Urgency", style="yellow")
        
        for loop in loops:
            urgency = loop.get("urgency", 0)
            urgency_style = "red" if urgency > 70 else ("yellow" if urgency > 30 else "green")
            
            table.add_row(
                loop.get("type", "-"),
                loop.get("prompt", "-"),
                f"[{urgency_style}]{urgency}%[/{urgency_style}]",
            )
        
        console.print(table)
    else:
        console.print("[green]No open loops! You're all caught up.[/green]")


@app.command()
def summarize(
    period: str = typer.Argument("week", help="Period to summarize: day, week, month"),
):
    """Summarize a time period."""
    setup_logging()
    
    with console.status(f"Summarizing the past {period}..."):
        crew = get_crew_instance()
        result = crew.query(f"Summarize what happened in the past {period}")
    
    if result.success and result.answer:
        console.print(Panel(
            Markdown(result.answer),
            title=f"Summary: Past {period.title()}",
        ))
    else:
        console.print("[dim]Nothing to summarize[/dim]")


@app.command()
def init():
    """Initialize the data directory and Neo4j schema."""
    setup_logging()
    
    console.print("[bold]Initializing Story of My Life...[/bold]\n")
    
    # Create directories
    console.print("Creating data directories...")
    settings.ensure_directories()
    console.print(f"  ✓ Data directory: {settings.data_dir}")
    
    # Initialize Neo4j
    console.print("\nInitializing Neo4j schema...")
    try:
        import subprocess
        subprocess.run(
            ["python", "scripts/init_neo4j.py"],
            check=True,
            cwd=settings.data_dir.parent,
        )
        console.print("  ✓ Neo4j schema initialized")
    except Exception as e:
        console.print(f"  [yellow]⚠ Neo4j initialization skipped: {e}[/yellow]")
    
    console.print("\n[green]✓ Initialization complete![/green]")


@app.command()
def status():
    """Show system status."""
    setup_logging()
    
    from soml.storage.registry import RegistryStore
    from soml.storage.graph import GraphStore
    from soml.core.types import EntityType
    
    console.print("[bold]Story of My Life Status[/bold]\n")
    
    # Data directory
    console.print(f"Data directory: {settings.data_dir}")
    console.print(f"  Exists: {'✓' if settings.data_dir.exists() else '✗'}")
    
    # Document counts
    registry = RegistryStore()
    counts = {}
    for entity_type in [EntityType.PERSON, EntityType.PROJECT, EntityType.GOAL, EntityType.NOTE, EntityType.EVENT, EntityType.PERIOD]:
        docs = registry.list_by_type(entity_type)
        counts[entity_type.value] = len(docs)
    
    console.print("\nDocument counts:")
    for doc_type, count in counts.items():
        console.print(f"  {doc_type}: {count}")
    
    # Neo4j connection
    console.print("\nNeo4j:")
    console.print(f"  URI: {settings.neo4j_uri}")
    try:
        graph = GraphStore()
        graph.driver.verify_connectivity()
        console.print("  Status: [green]Connected[/green]")
        graph.close()
    except Exception as e:
        console.print(f"  Status: [red]Not connected ({e})[/red]")
    
    # LLM configuration
    console.print("\nLLM:")
    console.print(f"  Provider: {settings.default_llm}")
    console.print(f"  API Key: {'✓ Set' if settings.openai_api_key or settings.anthropic_api_key else '✗ Not set'}")


if __name__ == "__main__":
    app()

