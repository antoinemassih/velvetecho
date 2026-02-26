"""
Complete example: Whalefin orchestrating Lobsterclaws + Urchinspike via Temporal.

This demonstrates the exact pattern requested:
1. Whalefin defines workflow
2. Workflow calls Lobsterclaws agents (via sessions)
3. Agents call tools (via Urchinspike)
4. Fan-out to 5 agents in parallel
5. Gather results and synthesize

Architecture:
    Whalefin (Temporal Workflow)
        ↓
    Lobsterclaws (Agent Sessions)
        ↓
    Urchinspike (Tool Execution)
"""

import asyncio
from typing import Dict, List, Any
from velvetecho.config import VelvetEchoConfig, init_config
from velvetecho.tasks import workflow, activity, WorkerManager, get_client, init_client
from velvetecho.communication import RPCClient, init_rpc_client, get_rpc_client
from velvetecho.patterns.multi_service import ServiceOrchestrator

# ============================================================================
# Configuration
# ============================================================================

# VelvetEcho config for Whalefin
config = VelvetEchoConfig(
    service_name="whalefin",
    temporal_host="localhost:7233",
    temporal_namespace="whalefin",
    temporal_worker_count=4,
)
init_config(config)

# RPC client for service communication
rpc = init_rpc_client(
    services={
        "lobsterclaws": "http://localhost:8001",
        "urchinspike": "http://localhost:8003",
    },
    timeout=180
)

# Service orchestrator helper
orchestrator = ServiceOrchestrator(rpc)


# ============================================================================
# Activities (Service Calls)
# ============================================================================

@activity(start_to_close_timeout=30, retry_policy={"max_attempts": 3})
async def start_agent_session(agent_id: str, context: Dict[str, Any]) -> str:
    """
    Start a Lobsterclaws agent session.

    Returns session_id for subsequent calls.
    """
    return await orchestrator.start_session(agent_id, context)


@activity(start_to_close_timeout=180, retry_policy={"max_attempts": 2})
async def send_agent_message(session_id: str, message: str) -> Dict[str, Any]:
    """
    Send message to agent via Lobsterclaws session.

    LLM call can take 30-180 seconds.
    """
    return await orchestrator.agent_message(session_id, message, timeout=180)


@activity(start_to_close_timeout=60, retry_policy={"max_attempts": 3})
async def execute_tool(session_id: str, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute tool via Lobsterclaws session.

    Lobsterclaws routes to Urchinspike.
    """
    return await orchestrator.execute_tool(session_id, tool, args)


@activity(start_to_close_timeout=30)
async def close_agent_session(session_id: str) -> None:
    """Close Lobsterclaws session"""
    await orchestrator.close_session(session_id)


# ============================================================================
# Workflows (Orchestration Logic)
# ============================================================================

@workflow(execution_timeout=3600)  # 1 hour max
async def code_analysis_workflow(
    repository_path: str,
    analysis_type: str = "full"
) -> Dict[str, Any]:
    """
    Multi-agent code analysis workflow.

    Steps:
    1. Start code analyst session
    2. Get initial analysis
    3. Execute tools based on analysis
    4. Fan-out to 5 specialized agents (parallel)
    5. Synthesize results
    6. Return comprehensive analysis

    Args:
        repository_path: Path to code repository
        analysis_type: Type of analysis (quick, full, deep)

    Returns:
        Comprehensive analysis results
    """
    print(f"\n{'='*60}")
    print(f"Starting Code Analysis Workflow")
    print(f"Repository: {repository_path}")
    print(f"Type: {analysis_type}")
    print(f"{'='*60}\n")

    # Step 1: Start code analyst session
    print("Step 1: Starting code analyst session...")
    session_id = await start_agent_session.run(
        agent_id="code-analyst",
        context={
            "repository": repository_path,
            "analysis_type": analysis_type
        }
    )
    print(f"✓ Session started: {session_id}\n")

    # Step 2: Get initial analysis
    print("Step 2: Getting initial analysis from agent...")
    initial_analysis = await send_agent_message.run(
        session_id=session_id,
        message=f"Analyze repository structure at {repository_path}. "
                f"Identify key files, architecture, and areas needing attention."
    )
    print(f"✓ Initial analysis complete")
    print(f"  Files identified: {initial_analysis.get('file_count', 'N/A')}")
    print(f"  Key file: {initial_analysis.get('key_file', 'N/A')}\n")

    # Step 3: Execute tools based on analysis
    print("Step 3: Reading key file...")
    key_file = initial_analysis.get("key_file", "README.md")
    file_content = await execute_tool.run(
        session_id=session_id,
        tool="read_file",
        args={"path": f"{repository_path}/{key_file}"}
    )
    print(f"✓ File read: {len(file_content.get('content', ''))} characters\n")

    # Step 4: Fan-out to 5 specialized agents (PARALLEL)
    print("Step 4: Fanning out to 5 specialized agents (parallel)...")

    specialized_prompts = [
        "Analyze code quality and patterns",
        "Identify security vulnerabilities",
        "Assess performance bottlenecks",
        "Review test coverage",
        "Evaluate documentation completeness"
    ]

    # Execute all 5 agents in parallel via asyncio.gather
    parallel_tasks = [
        send_agent_message.run(session_id=session_id, message=prompt)
        for prompt in specialized_prompts
    ]

    parallel_results = await asyncio.gather(*parallel_tasks)

    print(f"✓ All 5 agents completed")
    for i, result in enumerate(parallel_results, 1):
        status = result.get('status', 'unknown')
        print(f"  Agent {i}: {status}")
    print()

    # Step 5: Synthesize results
    print("Step 5: Synthesizing results...")
    synthesis_prompt = f"""
    Synthesize these specialized analyses into a comprehensive report:

    Initial Analysis: {initial_analysis}

    Specialized Analyses:
    1. Code Quality: {parallel_results[0]}
    2. Security: {parallel_results[1]}
    3. Performance: {parallel_results[2]}
    4. Testing: {parallel_results[3]}
    5. Documentation: {parallel_results[4]}

    Provide:
    - Overall assessment
    - Top 3 priorities
    - Recommended next steps
    """

    final_synthesis = await send_agent_message.run(
        session_id=session_id,
        message=synthesis_prompt
    )
    print(f"✓ Synthesis complete\n")

    # Step 6: Close session
    print("Step 6: Closing session...")
    await close_agent_session.run(session_id)
    print(f"✓ Session closed\n")

    print(f"{'='*60}")
    print("Workflow Complete!")
    print(f"{'='*60}\n")

    return {
        "session_id": session_id,
        "repository": repository_path,
        "initial_analysis": initial_analysis,
        "specialized_analyses": parallel_results,
        "synthesis": final_synthesis,
        "status": "completed"
    }


@workflow(execution_timeout=3600)
async def iterative_refinement_workflow(
    task: str,
    max_iterations: int = 3
) -> Dict[str, Any]:
    """
    Iterative refinement workflow with loop-back.

    Demonstrates:
    - Starting session
    - Loop with condition
    - Agent evaluation
    - Tool execution in loop
    - Conditional loop-back

    Args:
        task: Task to refine
        max_iterations: Maximum refinement iterations

    Returns:
        Refined result
    """
    print(f"\n{'='*60}")
    print(f"Starting Iterative Refinement Workflow")
    print(f"Task: {task}")
    print(f"Max Iterations: {max_iterations}")
    print(f"{'='*60}\n")

    # Start session
    session_id = await start_agent_session.run(
        agent_id="refinement-agent",
        context={"task": task}
    )

    iterations = []
    current_result = None

    for iteration in range(max_iterations):
        print(f"Iteration {iteration + 1}/{max_iterations}")

        # Generate solution
        if iteration == 0:
            prompt = f"Generate initial solution for: {task}"
        else:
            prompt = f"Refine previous solution based on evaluation: {current_result}"

        solution = await send_agent_message.run(session_id, prompt)

        # Evaluate solution
        evaluation = await send_agent_message.run(
            session_id,
            f"Evaluate solution quality (1-10): {solution}"
        )

        score = evaluation.get("quality_score", 0)
        print(f"  Quality score: {score}/10")

        iterations.append({
            "iteration": iteration + 1,
            "solution": solution,
            "evaluation": evaluation,
            "score": score
        })

        current_result = solution

        # Break if quality threshold met
        if score >= 8:
            print(f"  ✓ Quality threshold met!\n")
            break

        print(f"  → Refining...\n")

    # Close session
    await close_agent_session.run(session_id)

    print(f"{'='*60}")
    print("Refinement Complete!")
    print(f"Final Score: {iterations[-1]['score']}/10")
    print(f"{'='*60}\n")

    return {
        "task": task,
        "iterations": iterations,
        "final_result": current_result,
        "total_iterations": len(iterations),
        "status": "completed"
    }


# ============================================================================
# Worker
# ============================================================================

async def run_worker():
    """Start Whalefin Temporal worker"""
    await rpc.connect()

    worker = WorkerManager(
        config=config,
        workflows=[
            code_analysis_workflow,
            iterative_refinement_workflow,
        ],
        activities=[
            start_agent_session,
            send_agent_message,
            execute_tool,
            close_agent_session,
        ],
    )

    print(f"{'='*60}")
    print("Whalefin Worker Starting")
    print(f"{'='*60}")
    print(f"Task Queue: {config.task_queue}")
    print(f"Workers: {config.temporal_worker_count}")
    print(f"Services:")
    print(f"  - Lobsterclaws: {rpc.services['lobsterclaws']}")
    print(f"  - Urchinspike: {rpc.services['urchinspike']}")
    print(f"{'='*60}\n")

    await worker.start()


# ============================================================================
# Client (Trigger Workflows)
# ============================================================================

async def trigger_code_analysis():
    """Trigger code analysis workflow"""
    client = init_client(config)
    await client.connect()

    print("Triggering code analysis workflow...")

    handle = await client.start_workflow(
        code_analysis_workflow,
        "/path/to/repository",
        "full",
        workflow_id=f"code-analysis-{int(asyncio.get_event_loop().time())}"
    )

    print(f"Workflow started: {handle.id}")
    print("Waiting for result...\n")

    result = await handle.result()

    print("\n" + "="*60)
    print("FINAL RESULT")
    print("="*60)
    print(f"Status: {result['status']}")
    print(f"Repository: {result['repository']}")
    print(f"Synthesis: {result['synthesis']}")

    await client.disconnect()


async def trigger_iterative_refinement():
    """Trigger iterative refinement workflow"""
    client = init_client(config)
    await client.connect()

    print("Triggering iterative refinement workflow...")

    handle = await client.start_workflow(
        iterative_refinement_workflow,
        "Design a scalable API architecture",
        3,
        workflow_id=f"refinement-{int(asyncio.get_event_loop().time())}"
    )

    print(f"Workflow started: {handle.id}")
    print("Waiting for result...\n")

    result = await handle.result()

    print("\n" + "="*60)
    print("FINAL RESULT")
    print("="*60)
    print(f"Total Iterations: {result['total_iterations']}")
    print(f"Final Result: {result['final_result']}")

    await client.disconnect()


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python whalefin_orchestration.py worker")
        print("  python whalefin_orchestration.py analysis")
        print("  python whalefin_orchestration.py refinement")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "worker":
        asyncio.run(run_worker())
    elif mode == "analysis":
        asyncio.run(trigger_code_analysis())
    elif mode == "refinement":
        asyncio.run(trigger_iterative_refinement())
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
