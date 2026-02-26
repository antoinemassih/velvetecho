"""
Setup PatientComet database tables.

This script creates all tables needed for the PatientComet integration.
"""

import asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import models from the integration example
import sys
sys.path.insert(0, "../examples")

try:
    from patientcomet_full_integration import (
        Workspace,
        AnalyzerRun,
        AnalyzerResult,
        BaseModel,
    )
except ImportError:
    print("Error: Could not import models from patientcomet_full_integration.py")
    print("Make sure you're running from the VelvetEcho directory")
    sys.exit(1)


async def setup_database():
    """Create all tables"""
    # Async engine for creating tables
    engine = create_async_engine(
        "postgresql+asyncpg://velvetecho:password@localhost/patientcomet",
        echo=True,
    )

    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)

    print("\n✅ Database setup complete!")
    print("\nTables created:")
    print("  - workspaces")
    print("  - analyzer_runs")
    print("  - analyzer_results")

    await engine.dispose()


async def insert_test_data():
    """Insert sample data for testing"""
    engine = create_async_engine(
        "postgresql+asyncpg://velvetecho:password@localhost/patientcomet"
    )

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Create test workspace
        workspace = Workspace(
            name="Sample Project",
            path="/path/to/sample/project",
            description="Sample workspace for testing",
            language="python",
            framework="fastapi",
        )
        session.add(workspace)
        await session.commit()

        print(f"\n✅ Test data inserted!")
        print(f"   Workspace ID: {workspace.id}")

    await engine.dispose()


async def main():
    """Main setup function"""
    print("=" * 60)
    print("PatientComet Database Setup")
    print("=" * 60)
    print()

    try:
        await setup_database()

        # Ask if user wants test data
        response = input("\nInsert test data? (y/n): ")
        if response.lower() == 'y':
            await insert_test_data()

        print("\n" + "=" * 60)
        print("Setup complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Start worker: python examples/patientcomet_full_integration.py worker")
        print("2. Start API: python examples/patientcomet_full_integration.py api")
        print("3. Test API: curl http://localhost:9800/api/workspaces")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("1. PostgreSQL is running (docker-compose up postgres)")
        print("2. Database 'patientcomet' exists")
        print("3. User 'velvetecho' has access")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
