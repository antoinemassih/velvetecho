"""
Database migration utilities using Alembic.

Provides helpers for schema evolution and migration management.
"""

import os
from pathlib import Path
from typing import Optional, List
from alembic.config import Config
from alembic import command
from sqlalchemy.ext.asyncio import AsyncEngine


# ============================================================================
# Migration Manager
# ============================================================================


class MigrationManager:
    """
    Alembic migration manager.

    Example:
        from velvetecho.database import init_database, MigrationManager

        # Initialize database
        db = init_database("postgresql+asyncpg://user:pass@localhost/mydb")

        # Create migration manager
        manager = MigrationManager(
            db_url="postgresql://user:pass@localhost/mydb",  # Sync URL for Alembic
            migrations_dir="./migrations"
        )

        # Initialize migrations (first time)
        manager.init()

        # Auto-generate migration from models
        manager.create_migration("add_users_table")

        # Apply migrations
        manager.upgrade()

        # Rollback
        manager.downgrade(steps=1)
    """

    def __init__(
        self,
        db_url: str,
        migrations_dir: str = "./migrations",
        script_location: Optional[str] = None,
    ):
        """
        Initialize migration manager.

        Args:
            db_url: Sync database URL (e.g., postgresql://user:pass@localhost/db)
            migrations_dir: Directory for migration files
            script_location: Alembic script location (defaults to migrations_dir)
        """
        self.db_url = db_url
        self.migrations_dir = Path(migrations_dir)
        self.script_location = script_location or str(self.migrations_dir)

        # Create Alembic config
        self.config = self._create_config()

    def _create_config(self) -> Config:
        """Create Alembic configuration"""
        config = Config()
        config.set_main_option("script_location", self.script_location)
        config.set_main_option("sqlalchemy.url", self.db_url)

        # Set file template
        config.set_main_option(
            "file_template", "%%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(slug)s"
        )

        return config

    def init(self):
        """
        Initialize migrations directory.

        Creates Alembic directory structure:
        migrations/
        ├── alembic.ini
        ├── env.py
        ├── script.py.mako
        └── versions/
        """
        command.init(self.config, self.script_location)
        print(f"✅ Initialized migrations at {self.migrations_dir}")
        print("\nNext steps:")
        print(f"1. Edit {self.migrations_dir}/env.py to import your models")
        print("2. Run: create_migration('initial')")
        print("3. Run: upgrade()")

    def create_migration(
        self,
        message: str,
        autogenerate: bool = True,
    ) -> Optional[str]:
        """
        Create a new migration.

        Args:
            message: Migration message (e.g., "add_users_table")
            autogenerate: Auto-detect changes from models

        Returns:
            Migration revision ID

        Example:
            # Auto-generate from model changes
            revision = manager.create_migration("add_users_table")

            # Empty migration (manual SQL)
            revision = manager.create_migration("custom_sql", autogenerate=False)
        """
        try:
            revision = command.revision(
                self.config,
                message=message,
                autogenerate=autogenerate,
            )
            print(f"✅ Created migration: {message}")
            return revision.revision if hasattr(revision, "revision") else None
        except Exception as e:
            print(f"❌ Failed to create migration: {e}")
            return None

    def upgrade(self, revision: str = "head"):
        """
        Apply migrations.

        Args:
            revision: Target revision (default: "head" = latest)

        Example:
            # Upgrade to latest
            manager.upgrade()

            # Upgrade to specific revision
            manager.upgrade("abc123")

            # Upgrade by steps
            manager.upgrade("+1")  # One step forward
        """
        try:
            command.upgrade(self.config, revision)
            print(f"✅ Upgraded database to {revision}")
        except Exception as e:
            print(f"❌ Failed to upgrade: {e}")
            raise

    def downgrade(self, steps: int = 1):
        """
        Rollback migrations.

        Args:
            steps: Number of steps to rollback (default: 1)

        Example:
            # Rollback one migration
            manager.downgrade(steps=1)

            # Rollback to specific revision
            manager.downgrade_to("abc123")

            # Rollback all
            manager.downgrade_to("base")
        """
        try:
            revision = f"-{steps}"
            command.downgrade(self.config, revision)
            print(f"✅ Downgraded database by {steps} step(s)")
        except Exception as e:
            print(f"❌ Failed to downgrade: {e}")
            raise

    def downgrade_to(self, revision: str):
        """
        Rollback to specific revision.

        Args:
            revision: Target revision or "base" for initial state

        Example:
            # Rollback to specific revision
            manager.downgrade_to("abc123")

            # Rollback all migrations
            manager.downgrade_to("base")
        """
        try:
            command.downgrade(self.config, revision)
            print(f"✅ Downgraded database to {revision}")
        except Exception as e:
            print(f"❌ Failed to downgrade: {e}")
            raise

    def current(self):
        """
        Show current migration revision.

        Example:
            manager.current()
            # Output: Current revision: abc123
        """
        try:
            command.current(self.config)
        except Exception as e:
            print(f"❌ Failed to get current revision: {e}")

    def history(self, limit: int = 10):
        """
        Show migration history.

        Args:
            limit: Number of migrations to show (default: 10)

        Example:
            manager.history(limit=5)
        """
        try:
            command.history(self.config, rev_range=f"-{limit}:")
        except Exception as e:
            print(f"❌ Failed to get history: {e}")

    def stamp(self, revision: str):
        """
        Stamp database with specific revision (without running migrations).

        Useful when:
        - Migrating from existing database
        - Skipping migrations

        Args:
            revision: Revision to stamp or "head" for latest

        Example:
            # Mark database as up-to-date without running migrations
            manager.stamp("head")

            # Mark specific revision
            manager.stamp("abc123")
        """
        try:
            command.stamp(self.config, revision)
            print(f"✅ Stamped database with revision {revision}")
        except Exception as e:
            print(f"❌ Failed to stamp: {e}")
            raise


# ============================================================================
# Helper Functions
# ============================================================================


def convert_async_url_to_sync(async_url: str) -> str:
    """
    Convert async database URL to sync URL for Alembic.

    Alembic requires sync SQLAlchemy URLs.

    Example:
        async_url = "postgresql+asyncpg://user:pass@localhost/db"
        sync_url = convert_async_url_to_sync(async_url)
        # Result: "postgresql://user:pass@localhost/db"
    """
    return async_url.replace("+asyncpg", "").replace("+aiomysql", "").replace("+aiosqlite", "")


def create_env_py_template(target_metadata) -> str:
    """
    Create env.py template for Alembic.

    Returns:
        env.py content as string

    Usage:
        # In migrations/env.py
        from myapp.models import Base
        target_metadata = Base.metadata

        # Or use this function
        from velvetecho.database.migrations import create_env_py_template
        # Copy output to migrations/env.py
    """
    return """
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import your models here
# from myapp.models import Base
# target_metadata = Base.metadata

config = context.config
fileConfig(config.config_file_name)

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
"""


# ============================================================================
# CLI Integration
# ============================================================================


def create_migration_cli(manager: MigrationManager):
    """
    Create CLI for migrations.

    Example:
        # In your main.py or manage.py
        from velvetecho.database import init_database, MigrationManager
        from velvetecho.database.migrations import create_migration_cli

        db = init_database("postgresql+asyncpg://...")
        manager = MigrationManager(
            db_url="postgresql://...",  # Sync URL
            migrations_dir="./migrations"
        )

        cli = create_migration_cli(manager)

        if __name__ == "__main__":
            import sys
            if len(sys.argv) > 1:
                command = sys.argv[1]
                if command == "init":
                    manager.init()
                elif command == "create":
                    message = sys.argv[2] if len(sys.argv) > 2 else "migration"
                    manager.create_migration(message)
                elif command == "upgrade":
                    manager.upgrade()
                elif command == "downgrade":
                    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1
                    manager.downgrade(steps)
                elif command == "current":
                    manager.current()
                elif command == "history":
                    manager.history()
    """
    import argparse

    parser = argparse.ArgumentParser(description="Database migrations")
    parser.add_argument("command", choices=["init", "create", "upgrade", "downgrade", "current", "history"])
    parser.add_argument("args", nargs="*")

    return parser


# ============================================================================
# FastAPI Integration
# ============================================================================


def add_migration_endpoints(app, manager: MigrationManager):
    """
    Add migration endpoints to FastAPI app (for development only).

    WARNING: Do NOT expose these endpoints in production!

    Example:
        from fastapi import FastAPI
        from velvetecho.database import MigrationManager
        from velvetecho.database.migrations import add_migration_endpoints

        app = FastAPI()
        manager = MigrationManager(...)

        # Development only!
        if os.getenv("ENV") == "development":
            add_migration_endpoints(app, manager)
    """
    from fastapi import HTTPException

    @app.post("/admin/migrations/create")
    async def create_migration_endpoint(message: str):
        """Create new migration"""
        revision = manager.create_migration(message)
        return {"revision": revision, "message": message}

    @app.post("/admin/migrations/upgrade")
    async def upgrade_endpoint(revision: str = "head"):
        """Apply migrations"""
        try:
            manager.upgrade(revision)
            return {"status": "success", "revision": revision}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/admin/migrations/downgrade")
    async def downgrade_endpoint(steps: int = 1):
        """Rollback migrations"""
        try:
            manager.downgrade(steps)
            return {"status": "success", "steps": steps}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/admin/migrations/current")
    async def current_endpoint():
        """Get current revision"""
        # Note: This would need to capture output
        manager.current()
        return {"status": "check logs"}

    @app.get("/admin/migrations/history")
    async def history_endpoint(limit: int = 10):
        """Get migration history"""
        # Note: This would need to capture output
        manager.history(limit)
        return {"status": "check logs"}
