"""
Setup Lobsterclaws database tables.

This script creates all tables needed for the Lobsterclaws integration.
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import models from the integration example
import sys
sys.path.insert(0, "../examples")

try:
    from lobsterclaws_full_integration import (
        AgentDefinition,
        AgentSession,
        ExecutionLog,
        BaseModel,
        AgentCategory,
    )
except ImportError:
    print("Error: Could not import models from lobsterclaws_full_integration.py")
    print("Make sure you're running from the VelvetEcho directory")
    sys.exit(1)


async def setup_database():
    """Create all tables"""
    # Async engine for creating tables
    engine = create_async_engine(
        "postgresql+asyncpg://velvetecho:password@localhost/lobsterclaws",
        echo=True,
    )

    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)

    print("\n✅ Database setup complete!")
    print("\nTables created:")
    print("  - agent_definitions")
    print("  - agent_sessions")
    print("  - execution_logs")

    await engine.dispose()


async def insert_test_data():
    """Insert sample data for testing"""
    engine = create_async_engine(
        "postgresql+asyncpg://velvetecho:password@localhost/lobsterclaws"
    )

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Create test agent
        agent = AgentDefinition(
            agent_id="sample_code_analyst",
            name="Sample Code Analyst",
            description="A sample agent for testing",
            category=AgentCategory.CODE_ANALYSIS,
            model="claude-sonnet-4.5",
            tools=["read_file", "write_file", "execute_command"],
            system_prompt="You are a helpful code analyst assistant.",
            metadata={"test": True},
        )
        session.add(agent)
        await session.commit()

        print(f"\n✅ Test data inserted!")
        print(f"   Agent ID: {agent.id}")
        print(f"   Agent Key: {agent.agent_id}")

    await engine.dispose()


async def main():
    """Main setup function"""
    print("=" * 60)
    print("Lobsterclaws Database Setup")
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
        print("1. Start worker: python examples/lobsterclaws_full_integration.py worker")
        print("2. Start API: python examples/lobsterclaws_full_integration.py api")
        print("3. Test API: curl http://localhost:9720/api/agents")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("1. PostgreSQL is running (docker-compose up postgres)")
        print("2. Database 'lobsterclaws' exists")
        print("3. User 'velvetecho' has access")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
