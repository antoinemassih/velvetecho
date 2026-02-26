# VelvetEcho

**Distributed task orchestration and API infrastructure for microservices**

VelvetEcho provides a unified foundation for building scalable microservices with:
- **Task Orchestration**: Temporal-based workflows with dependencies, retries, and parallelism
- **API Framework**: FastAPI patterns with standardized responses and error handling
- **Cache Layer**: Redis-backed caching with circuit breakers and smart patterns
- **Queue Management**: Priority queues, delayed tasks, and dead letter queues
- **Observability**: Built-in metrics, tracing, and structured logging

## Architecture

VelvetEcho is designed as a **library, not a service**. Each microservice:
- Installs VelvetEcho as a dependency
- Runs its own Temporal worker pool
- Connects to shared infrastructure (Temporal cluster, Redis)
- Maintains full independence

## Installation

```bash
# From PyPI (once published)
pip install velvetecho

# From git (development)
pip install git+https://github.com/yourusername/velvetecho.git

# Poetry
poetry add velvetecho
```

## Quick Start

### 1. Configure

```python
from velvetecho.config import VelvetEchoConfig

config = VelvetEchoConfig(
    service_name="my-service",
    temporal_host="localhost:7233",
    temporal_namespace="default",
    redis_url="redis://localhost:6379/0",
    task_queue="my-service-tasks"
)
```

### 2. Define Workflows

```python
from velvetecho.tasks import workflow, activity

@activity
async def fetch_data(url: str) -> dict:
    """Activities are individual units of work"""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

@workflow
async def process_pipeline(input_url: str):
    """Workflows orchestrate activities"""
    data = await fetch_data.run(input_url)
    result = await transform_data.run(data)
    await save_result.run(result)
    return result
```

### 3. Run Workers

```python
from velvetecho.tasks import WorkerManager

async def main():
    worker = WorkerManager(config)
    await worker.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### 4. Trigger from API

```python
from fastapi import FastAPI
from velvetecho.api import StandardResponse
from velvetecho.tasks import get_client

app = FastAPI()

@app.post("/process")
async def trigger_process(url: str):
    client = get_client()
    handle = await process_pipeline.start(url)
    return StandardResponse(data={"workflow_id": handle.id})
```

## Project Status

**Phase 1: Task Orchestration** (In Progress)
- ✅ Project structure
- 🚧 Temporal workflow wrappers
- 🚧 Activity decorators
- 🚧 Worker management
- ⏳ Dependency chains
- ⏳ Parallel execution

**Phase 2: API Framework** (Planned)
- Standard responses
- Error handling
- Middleware patterns

**Phase 3: Cache & Queue** (Planned)
- Redis patterns
- Circuit breakers
- Priority queues

## Services Using VelvetEcho

- **PatientComet** (Pilot): Code intelligence pipeline with 111 DAG analyzers
- **Whalefin**: Workflow engine with 6 node types
- **Lobsterclaws**: WebSocket gateway and session management
- **NeonPlane**: Visual workflow orchestration
- **CoralBeef**: (TBD)
- **LunarBadger**: (TBD)

## Development

```bash
# Clone repo
git clone https://github.com/yourusername/velvetecho.git
cd velvetecho

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Format code
poetry run black velvetecho tests
poetry run ruff velvetecho tests

# Type check
poetry run mypy velvetecho
```

## License

MIT
