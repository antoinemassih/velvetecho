"""
VelvetEcho CLI - Main Entry Point

Usage:
    velvetecho generate resource Agent name:str description:text --timestamps
    velvetecho generate model Agent name:str
    velvetecho init my-project
"""

import click
from pathlib import Path
from typing import Optional
from velvetecho.cli.generators import ResourceGenerator


@click.group()
@click.version_option(version="2.0.0")
def cli():
    """
    VelvetEcho CLI - Enterprise workflow orchestration toolkit

    \b
    Examples:
        # Generate complete resource (model + schemas + router)
        velvetecho generate resource Agent name:str type:str --timestamps

        # Generate just model
        velvetecho generate model Agent name:str description:text

        # Initialize new project
        velvetecho init my-project

        # Run development server
        velvetecho dev
    """
    pass


@cli.group()
def generate():
    """Generate code (models, schemas, routers, resources)"""
    pass


@generate.command()
@click.argument("name")
@click.argument("fields", nargs=-1)
@click.option("--timestamps", is_flag=True, help="Add created_at/updated_at fields")
@click.option("--soft-delete", is_flag=True, help="Add deleted_at field (soft delete)")
@click.option("--output", "-o", type=Path, help="Output directory (default: current)")
def resource(name: str, fields: tuple[str], timestamps: bool, soft_delete: bool, output: Optional[Path]):
    """
    Generate complete resource (model + schemas + router + migration)

    \b
    Examples:
        velvetecho generate resource Agent name:str type:str --timestamps
        velvetecho generate resource Workspace name:str description:text created_by:str --timestamps --soft-delete
        velvetecho generate resource Project name:str workspace_id:uuid status:str

    \b
    Field Format:
        name:type
        - str, text, int, float, bool, uuid, datetime, json
        - Add ? for optional: name:str?
    """
    output_dir = output or Path.cwd()
    generator = ResourceGenerator(output_dir)

    try:
        result = generator.generate_resource(
            name=name,
            fields=list(fields),
            timestamps=timestamps,
            soft_delete=soft_delete,
        )

        click.echo(click.style("\n✅ Resource generated successfully!\n", fg="green", bold=True))
        click.echo(f"📁 Files created:")
        for file_path in result["files"]:
            click.echo(f"   ✅ {file_path}")

        click.echo(f"\n📡 Endpoints available:")
        for endpoint in result["endpoints"]:
            click.echo(f"   {endpoint}")

        click.echo(f"\n🚀 Next steps:")
        click.echo(f"   1. Run migration: alembic upgrade head")
        click.echo(f"   2. Start server: uvicorn velvetecho.api.app:app --reload")
        click.echo(f"   3. Visit: http://localhost:8000/docs")

    except Exception as e:
        click.echo(click.style(f"\n❌ Error: {e}", fg="red", bold=True))
        raise click.Abort()


@generate.command()
@click.argument("name")
@click.argument("fields", nargs=-1)
@click.option("--timestamps", is_flag=True, help="Add timestamp fields")
@click.option("--soft-delete", is_flag=True, help="Add soft delete")
def model(name: str, fields: tuple[str], timestamps: bool, soft_delete: bool):
    """
    Generate database model only

    \b
    Example:
        velvetecho generate model Agent name:str description:text --timestamps
    """
    output_dir = Path.cwd()
    generator = ResourceGenerator(output_dir)

    result = generator.generate_model(
        name=name,
        fields=list(fields),
        timestamps=timestamps,
        soft_delete=soft_delete,
    )

    click.echo(click.style(f"\n✅ Model generated: {result['file']}", fg="green"))


@generate.command()
@click.argument("name")
@click.argument("fields", nargs=-1)
def schemas(name: str, fields: tuple[str]):
    """
    Generate Pydantic schemas (Create/Update/Response)

    \b
    Example:
        velvetecho generate schemas Agent name:str description:text
    """
    output_dir = Path.cwd()
    generator = ResourceGenerator(output_dir)

    result = generator.generate_schemas(name=name, fields=list(fields))

    click.echo(click.style(f"\n✅ Schemas generated: {result['file']}", fg="green"))


@generate.command()
@click.argument("name")
@click.option("--crud", is_flag=True, help="Include CRUD routes")
def router(name: str, crud: bool):
    """
    Generate API router

    \b
    Example:
        velvetecho generate router agents --crud
    """
    output_dir = Path.cwd()
    generator = ResourceGenerator(output_dir)

    result = generator.generate_router(name=name, include_crud=crud)

    click.echo(click.style(f"\n✅ Router generated: {result['file']}", fg="green"))


@cli.command()
@click.argument("project_name")
@click.option("--template", "-t", default="api", help="Project template (api, fullstack)")
def init(project_name: str, template: str):
    """
    Initialize new VelvetEcho project

    \b
    Example:
        velvetecho init my-api
        cd my-api
        velvetecho dev
    """
    click.echo(f"🚀 Initializing project: {project_name}")
    click.echo(f"   Template: {template}")
    click.echo(click.style("\n⚠️  Not yet implemented - Coming soon!", fg="yellow"))


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind")
@click.option("--port", default=8000, help="Port to bind")
@click.option("--reload/--no-reload", default=True, help="Auto-reload on changes")
def dev(host: str, port: int, reload: bool):
    """
    Run development server with auto-reload

    \b
    Example:
        velvetecho dev
        velvetecho dev --port 8080 --no-reload
    """
    import uvicorn
    from velvetecho.api.app import app

    click.echo(f"🚀 Starting VelvetEcho development server...")
    click.echo(f"   Host: {host}")
    click.echo(f"   Port: {port}")
    click.echo(f"   Auto-reload: {reload}")
    click.echo(f"\n📡 API Docs: http://{host}:{port}/docs")
    click.echo(f"🔍 ReDoc: http://{host}:{port}/redoc\n")

    uvicorn.run("velvetecho.api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    cli()
