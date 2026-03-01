# PatientComet Integration Plan for VelvetEcho

**Date**: 2026-03-01
**Status**: Ready for Implementation
**Estimated Timeline**: 1-2 days

---

## 🎯 Integration Overview

**Goal**: Migrate PatientComet's 111-analyzer code intelligence pipeline to VelvetEcho's Temporal orchestration platform.

**Benefits**:
- ✅ **Parallel Execution**: 50+ analyzers run concurrently (Phase 2)
- ✅ **Durable Execution**: Survives crashes, automatic retries
- ✅ **Fault Tolerance**: Circuit breaker prevents cascading failures
- ✅ **Observability**: Full visibility via Temporal UI, Prometheus, Jaeger
- ✅ **Progress Tracking**: Real-time workflow state and visualization
- ✅ **Resource Management**: Better control over analyzer concurrency

---

## 📋 Current PatientComet Architecture

### Analyzer Pipeline (111 Analyzers)

**Execution Model**: Sequential execution via `DAGCoordinator`
- **Location**: `/Users/antoineabdul-massih/Documents/patientcomet/`
- **Port**: 9800
- **Database**: PostgreSQL (`patientcomet` database, `comet.*` schema)

**Analyzer Types**:
1. **Static Metadata** (Phase 1): File system, symbols, imports, libraries
2. **Dependency Analysis** (Phase 2): Call graphs, data flows, relationships
3. **Intelligence** (Phase 3): Predictions, patterns, security, quality
4. **Embeddings** (Phase 4): 3-pass vector embeddings

**Current Execution**:
```python
# patientcomet/core/coordinator.py
class DAGCoordinator:
    async def execute_run(self, run_id: UUID, profile: str):
        # Sequential execution with dependency resolution
        for analyzer in topologically_sorted_analyzers:
            await analyzer.execute()
```

---

## 🔄 VelvetEcho Migration Architecture

### New Workflow Structure

```
PatientCometAnalysisWorkflow (Temporal Workflow)
├── Phase 1: Foundation (no dependencies)
│   ├── file_system_analyzer
│   ├── symbol_extraction
│   ├── import_detection
│   └── library_detection (8 total)
│
├── Phase 2: Dependencies (parallel, depend on Phase 1)
│   ├── call_graph_builder
│   ├── type_resolver
│   ├── data_flow_analyzer
│   └── ... (50+ analyzers run in PARALLEL)
│
├── Phase 3: Intelligence (depend on Phase 2)
│   ├── performance_regression
│   ├── security_risk_scoring
│   ├── code_health
│   └── ... (30+ analyzers)
│
└── Phase 4: Embeddings & Finalization
    ├── embedding_pass_1 (raw signatures)
    ├── embedding_pass_2 (+relationships)
    └── embedding_pass_3 (+intelligence)
```

**Key Changes**:
- ✅ Phase 2 runs **in parallel** (50+ analyzers simultaneously)
- ✅ Automatic retry on failure
- ✅ Progress tracking per-analyzer
- ✅ Circuit breaker per analyzer (prevent cascading failures)

---

## 🏗️ Implementation Steps

### Step 1: Create Analyzer Activities (1-2 hours)

**File**: `velvetecho/patientcomet/activities.py`

Each analyzer becomes a Temporal activity:

```python
from temporalio import activity
from patientcomet.analyzers import SymbolExtractionAnalyzer

@activity.defn
async def analyze_symbols(workspace_id: str) -> dict:
    """Phase 1: Extract symbols from codebase"""
    analyzer = SymbolExtractionAnalyzer()
    await analyzer.initialize(workspace_id)
    result = await analyzer.execute()

    return {
        "analyzer_id": "symbol_extraction",
        "workspace_id": workspace_id,
        "symbols_count": len(result["symbols"]),
        "status": "completed",
        "output": result
    }

@activity.defn
async def analyze_call_graph(workspace_id: str, symbols: dict) -> dict:
    """Phase 2: Build call graph (depends on symbols)"""
    analyzer = CallGraphAnalyzer()
    await analyzer.initialize(workspace_id, dependencies={"symbols": symbols})
    result = await analyzer.execute()

    return {
        "analyzer_id": "call_graph",
        "workspace_id": workspace_id,
        "calls_count": len(result["calls"]),
        "status": "completed",
        "output": result
    }

# ... 109 more analyzer activities
```

---

### Step 2: Define DAG Workflow (2-3 hours)

**File**: `velvetecho/patientcomet/workflow.py`

```python
from temporalio import workflow
from datetime import timedelta
from velvetecho.patterns import DAGWorkflow, DAGNode
from .activities import *

@workflow.defn
class PatientCometAnalysisWorkflow:
    """
    Orchestrates 111 PatientComet analyzers in dependency order.

    Phases:
    1. Foundation (8 analyzers, no deps)
    2. Dependencies (50+ analyzers, parallel)
    3. Intelligence (30+ analyzers, depend on Phase 2)
    4. Embeddings (3 passes, sequential)
    """

    @workflow.run
    async def run(self, workspace_id: str, profile: str = "full") -> dict:
        dag = DAGWorkflow()

        # =============================================
        # PHASE 1: Foundation (No Dependencies)
        # =============================================

        # Symbol Extraction
        async def exec_symbols(dependencies, **kwargs):
            return await workflow.execute_activity(
                analyze_symbols,
                workspace_id,
                start_to_close_timeout=timedelta(seconds=300),  # 5 min
                retry_policy=workflow.RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=5),
                ),
            )

        dag.add_node(DAGNode(
            id="symbol_extraction",
            execute=exec_symbols,
            dependencies=[]
        ))

        # Import Detection
        async def exec_imports(dependencies, **kwargs):
            return await workflow.execute_activity(
                analyze_imports,
                workspace_id,
                start_to_close_timeout=timedelta(seconds=120),
            )

        dag.add_node(DAGNode(
            id="import_detection",
            execute=exec_imports,
            dependencies=[]
        ))

        # ... 6 more Phase 1 analyzers

        # =============================================
        # PHASE 2: Dependencies (50+ Parallel)
        # =============================================

        # Call Graph (depends on symbols)
        async def exec_call_graph(dependencies, **kwargs):
            symbols = dependencies["symbol_extraction"]
            return await workflow.execute_activity(
                analyze_call_graph,
                args=[workspace_id, symbols],
                start_to_close_timeout=timedelta(seconds=300),
            )

        dag.add_node(DAGNode(
            id="call_graph",
            execute=exec_call_graph,
            dependencies=["symbol_extraction"]
        ))

        # Type Resolution (depends on symbols + imports)
        async def exec_types(dependencies, **kwargs):
            symbols = dependencies["symbol_extraction"]
            imports = dependencies["import_detection"]
            return await workflow.execute_activity(
                analyze_types,
                args=[workspace_id, symbols, imports],
                start_to_close_timeout=timedelta(seconds=300),
            )

        dag.add_node(DAGNode(
            id="type_resolution",
            execute=exec_types,
            dependencies=["symbol_extraction", "import_detection"]
        ))

        # ... 48 more Phase 2 analyzers (all run in PARALLEL)

        # =============================================
        # PHASE 3: Intelligence (Depends on Phase 2)
        # =============================================

        # Security Risk Scoring (depends on call_graph, types, data_flows)
        async def exec_security(dependencies, **kwargs):
            call_graph = dependencies["call_graph"]
            types = dependencies["type_resolution"]
            data_flows = dependencies["data_flow_analysis"]

            return await workflow.execute_activity(
                analyze_security_risks,
                args=[workspace_id, call_graph, types, data_flows],
                start_to_close_timeout=timedelta(seconds=180),
            )

        dag.add_node(DAGNode(
            id="security_risk_scoring",
            execute=exec_security,
            dependencies=["call_graph", "type_resolution", "data_flow_analysis"]
        ))

        # ... 29 more Phase 3 analyzers

        # =============================================
        # PHASE 4: Embeddings (Sequential)
        # =============================================

        # Embedding Pass 1 (raw signatures)
        async def exec_embed_1(dependencies, **kwargs):
            symbols = dependencies["symbol_extraction"]
            return await workflow.execute_activity(
                generate_embeddings_pass1,
                args=[workspace_id, symbols],
                start_to_close_timeout=timedelta(seconds=600),  # 10 min
            )

        dag.add_node(DAGNode(
            id="embedding_pass_1",
            execute=exec_embed_1,
            dependencies=["symbol_extraction"]
        ))

        # Embedding Pass 2 (+relationships)
        async def exec_embed_2(dependencies, **kwargs):
            pass1 = dependencies["embedding_pass_1"]
            relationships = dependencies["relationship_analysis"]
            return await workflow.execute_activity(
                generate_embeddings_pass2,
                args=[workspace_id, pass1, relationships],
                start_to_close_timeout=timedelta(seconds=600),
            )

        dag.add_node(DAGNode(
            id="embedding_pass_2",
            execute=exec_embed_2,
            dependencies=["embedding_pass_1", "relationship_analysis"]
        ))

        # Embedding Pass 3 (+intelligence)
        async def exec_embed_3(dependencies, **kwargs):
            pass2 = dependencies["embedding_pass_2"]
            intelligence = dependencies["code_health"]
            return await workflow.execute_activity(
                generate_embeddings_pass3,
                args=[workspace_id, pass2, intelligence],
                start_to_close_timeout=timedelta(seconds=600),
            )

        dag.add_node(DAGNode(
            id="embedding_pass_3",
            execute=exec_embed_3,
            dependencies=["embedding_pass_2", "code_health"]
        ))

        # =============================================
        # Execute DAG
        # =============================================

        start_time = workflow.now()
        results = await dag.execute(workspace_id=workspace_id, profile=profile)
        elapsed = (workflow.now() - start_time).total_seconds()

        return {
            "workspace_id": workspace_id,
            "profile": profile,
            "analyzers_completed": len(results),
            "execution_time_seconds": elapsed,
            "status": "completed",
            "results": results
        }
```

---

### Step 3: Dependency Mapping (2-3 hours)

**File**: `velvetecho/patientcomet/dependency_map.py`

Map PatientComet analyzer dependencies:

```python
ANALYZER_DEPENDENCIES = {
    # Phase 1: Foundation (no dependencies)
    "symbol_extraction": [],
    "import_detection": [],
    "file_system_scan": [],
    "library_detection": [],
    "export_detection": [],
    "language_detection": [],
    "framework_detection": [],
    "env_var_detection": [],

    # Phase 2: Dependencies (parallel execution)
    "call_graph": ["symbol_extraction"],
    "type_resolution": ["symbol_extraction", "import_detection"],
    "data_flow_analysis": ["symbol_extraction", "call_graph"],
    "state_management": ["symbol_extraction", "call_graph"],
    "component_analysis": ["symbol_extraction", "framework_detection"],
    "hook_detection": ["symbol_extraction", "framework_detection"],
    "test_coverage": ["symbol_extraction", "import_detection"],
    "api_surface": ["symbol_extraction", "export_detection"],
    "schema_extraction": ["symbol_extraction", "type_resolution"],
    "error_handling": ["symbol_extraction", "call_graph"],
    # ... 40 more Phase 2 analyzers

    # Phase 3: Intelligence (depends on Phase 2)
    "security_risk_scoring": ["call_graph", "type_resolution", "data_flow_analysis"],
    "performance_regression": ["call_graph", "complexity_metrics"],
    "code_health": ["symbol_extraction", "test_coverage", "complexity_metrics"],
    "technical_debt": ["code_health", "complexity_metrics"],
    # ... 26 more Phase 3 analyzers

    # Phase 4: Embeddings
    "embedding_pass_1": ["symbol_extraction"],
    "embedding_pass_2": ["embedding_pass_1", "relationship_analysis"],
    "embedding_pass_3": ["embedding_pass_2", "code_health", "security_risk_scoring"],
}

# Profile definitions (which analyzers to run)
PROFILES = {
    "quick": [
        "symbol_extraction", "import_detection", "call_graph",
        "type_resolution", "embedding_pass_1"
    ],
    "full": list(ANALYZER_DEPENDENCIES.keys()),  # All 111
    "frontend": [
        "symbol_extraction", "component_analysis", "hook_detection",
        "style_analysis", "layout_patterns", "accessibility"
    ],
    "backend": [
        "symbol_extraction", "api_surface", "schema_extraction",
        "database_queries", "security_risk_scoring"
    ],
    "security": [
        "symbol_extraction", "security_risk_scoring", "vulnerability_detection",
        "data_flow_analysis", "input_validation"
    ],
}
```

---

### Step 4: Worker Setup (1 hour)

**File**: `velvetecho/patientcomet/worker.py`

```python
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from .workflow import PatientCometAnalysisWorkflow
from .activities import *

async def run_worker():
    """Start PatientComet analysis worker"""

    client = await Client.connect("localhost:7233")

    # Collect all analyzer activities
    activities = [
        analyze_symbols,
        analyze_imports,
        analyze_call_graph,
        analyze_types,
        # ... all 111 analyzer activities
    ]

    worker = Worker(
        client,
        task_queue="patientcomet-analysis",
        workflows=[PatientCometAnalysisWorkflow],
        activities=activities,
        max_concurrent_workflow_tasks=10,  # Run up to 10 workflows concurrently
        max_concurrent_activities=50,      # Run up to 50 analyzers in parallel
    )

    print("🚀 PatientComet worker started")
    print("   Task Queue: patientcomet-analysis")
    print("   Max Concurrent Workflows: 10")
    print("   Max Concurrent Activities: 50")
    print("   Temporal UI: http://localhost:8088")

    await worker.run()

if __name__ == "__main__":
    asyncio.run(run_worker())
```

---

### Step 5: Client API (1 hour)

**File**: `velvetecho/patientcomet/client.py`

```python
from temporalio.client import Client
from .workflow import PatientCometAnalysisWorkflow
import uuid

class PatientCometClient:
    """Client for triggering PatientComet analysis workflows"""

    def __init__(self, temporal_url: str = "localhost:7233"):
        self.temporal_url = temporal_url
        self.client = None

    async def connect(self):
        """Connect to Temporal"""
        self.client = await Client.connect(self.temporal_url)

    async def start_analysis(
        self,
        workspace_id: str,
        profile: str = "full"
    ) -> str:
        """
        Start PatientComet analysis workflow.

        Args:
            workspace_id: Workspace UUID
            profile: Analysis profile (quick, full, frontend, backend, security)

        Returns:
            Workflow execution ID
        """
        if not self.client:
            await self.connect()

        workflow_id = f"patientcomet-{workspace_id}-{uuid.uuid4()}"

        handle = await self.client.start_workflow(
            PatientCometAnalysisWorkflow.run,
            args=[workspace_id, profile],
            id=workflow_id,
            task_queue="patientcomet-analysis",
        )

        return handle.id

    async def get_status(self, workflow_id: str) -> dict:
        """Get workflow execution status"""
        handle = self.client.get_workflow_handle(workflow_id)
        description = await handle.describe()

        return {
            "workflow_id": workflow_id,
            "status": description.status.name,
            "start_time": description.start_time,
            "close_time": description.close_time,
        }

    async def get_result(self, workflow_id: str) -> dict:
        """Wait for workflow completion and get result"""
        handle = self.client.get_workflow_handle(workflow_id)
        return await handle.result()

# Usage example
async def main():
    client = PatientCometClient()

    # Start analysis
    workflow_id = await client.start_analysis(
        workspace_id="0caf2da3-...",
        profile="full"
    )

    print(f"Analysis started: {workflow_id}")
    print(f"View progress: http://localhost:8088")

    # Get result
    result = await client.get_result(workflow_id)
    print(f"Analysis complete: {result['analyzers_completed']} analyzers")
```

---

## 📊 Expected Performance Improvements

### Current (Sequential)

```
111 analyzers × ~2.4s average = ~266 seconds (4.4 minutes)
```

### With VelvetEcho (Parallel)

```
Phase 1: 8 analyzers × 2.4s = ~2.4s (sequential)
Phase 2: 50 analyzers ÷ 50 workers = ~2.4s (parallel!)
Phase 3: 30 analyzers ÷ 30 workers = ~2.4s (parallel!)
Phase 4: 3 passes × 10s = ~30s (sequential)

Total: ~37 seconds (7x faster!)
```

**Estimated Speedup**: **7x faster** (4.4 min → 37 sec)

---

## 🔧 Configuration

### VelvetEcho Config

**File**: `velvetecho/.env`

```bash
# Temporal
TEMPORAL_URL=localhost:7233

# PatientComet Database
PATIENTCOMET_DB_HOST=localhost
PATIENTCOMET_DB_PORT=5432
PATIENTCOMET_DB_NAME=patientcomet
PATIENTCOMET_DB_USER=your_user
PATIENTCOMET_DB_PASSWORD=your_password

# Worker Concurrency
PATIENTCOMET_MAX_CONCURRENT_WORKFLOWS=10
PATIENTCOMET_MAX_CONCURRENT_ACTIVITIES=50

# Timeouts
PATIENTCOMET_ANALYZER_TIMEOUT=300  # 5 minutes
PATIENTCOMET_EMBEDDING_TIMEOUT=600  # 10 minutes
```

---

## 🚀 Deployment Steps

### 1. Start Infrastructure

```bash
cd /Users/antoineabdul-massih/Documents/VelvetEcho
docker-compose up -d
```

**Services Started**:
- Temporal (port 7233)
- Temporal UI (port 8088)
- PostgreSQL (port 5432)
- Redis (port 6379)
- Prometheus (port 9090)
- Grafana (port 3000)
- Jaeger (port 16686)

### 2. Start Worker

```bash
python -m velvetecho.patientcomet.worker
```

### 3. Trigger Analysis (via API or Client)

```python
from velvetecho.patientcomet.client import PatientCometClient

client = PatientCometClient()
workflow_id = await client.start_analysis(
    workspace_id="0caf2da3-...",
    profile="full"
)
```

---

## 📈 Monitoring

### Temporal UI

**URL**: http://localhost:8088

**Features**:
- Live workflow execution status
- Per-analyzer progress tracking
- Retry history
- Error stack traces
- Execution timeline

### Prometheus Metrics

**URL**: http://localhost:9090

**Metrics Available**:
- `patientcomet_analyzer_duration_seconds`
- `patientcomet_analyzer_failures_total`
- `patientcomet_workflow_duration_seconds`
- `patientcomet_parallel_execution_count`

### Grafana Dashboards

**URL**: http://localhost:3000

**Dashboards**:
- PatientComet Analysis Overview
- Analyzer Performance
- Failure Analysis
- Resource Usage

---

## 🎯 Success Criteria

- ✅ All 111 analyzers execute successfully
- ✅ Execution time < 1 minute (7x improvement)
- ✅ Zero data loss (all results persisted)
- ✅ Automatic retry on transient failures
- ✅ Full observability (Temporal UI, metrics, logs)
- ✅ Resource usage < 4GB RAM, < 50% CPU

---

## 🔄 Migration Path

### Phase 1: Pilot (1-2 days)

1. ✅ Implement 10 core analyzers
2. ✅ Test with small workspace (134 files)
3. ✅ Verify results match existing pipeline
4. ✅ Performance benchmark

### Phase 2: Full Migration (3-5 days)

1. ✅ Implement all 111 analyzers
2. ✅ Test with large workspace (33K files)
3. ✅ Load testing (10 concurrent analyses)
4. ✅ Production deployment

### Phase 3: Optimization (ongoing)

1. ✅ Fine-tune concurrency limits
2. ✅ Add circuit breakers per analyzer type
3. ✅ Optimize slow analyzers
4. ✅ Add caching for expensive operations

---

## 🎓 Training & Documentation

### For PatientComet Team

**Required Reading**:
1. `VELVETECHO_GETTING_STARTED.md` - Quick start guide
2. `VELVETECHO_ARCHITECTURE.md` - System design
3. `VELVETECHO_API_REFERENCE.md` - API documentation
4. `VELVETECHO_MONITORING.md` - Operations guide

**Hands-On Labs**:
1. Running a simple workflow
2. Adding a new analyzer
3. Debugging failed workflows
4. Performance optimization

---

## 📞 Support

**VelvetEcho Issues**: https://github.com/velvetecho/velvetecho/issues
**PatientComet Integration**: Contact integration team
**Temporal Support**: https://temporal.io/docs

---

## ✅ Checklist

**Pre-Integration**:
- [ ] VelvetEcho infrastructure running
- [ ] PatientComet database accessible
- [ ] All 111 analyzers inventoried
- [ ] Dependency map complete

**Implementation**:
- [ ] Activity wrappers for all analyzers
- [ ] DAG workflow defined
- [ ] Worker configured
- [ ] Client API tested

**Testing**:
- [ ] Unit tests for activities
- [ ] Integration test (small workspace)
- [ ] Performance test (large workspace)
- [ ] Failure scenarios tested

**Deployment**:
- [ ] Production configuration
- [ ] Monitoring dashboards
- [ ] Alert rules configured
- [ ] Documentation complete

---

**Next Steps**: Proceed to implementation using this plan as the blueprint. Expected completion: 1-2 days for core integration, 3-5 days for full production readiness.
