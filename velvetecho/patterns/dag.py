"""DAG (Directed Acyclic Graph) execution pattern for workflows with dependencies"""

import asyncio
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque


@dataclass
class DAGNode:
    """
    A node in a DAG representing a single task.

    Example:
        node = DAGNode(
            id="analyze_symbols",
            execute=analyze_symbols_activity.run,
            dependencies=["parse_files"],
        )
    """

    id: str
    execute: Callable  # Activity function to execute
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DAGWorkflow:
    """
    Helper for executing workflows with DAG dependencies.

    Automatically:
    - Resolves topological order
    - Executes independent nodes in parallel
    - Passes dependency results to dependent nodes
    - Tracks execution progress

    Example:
        @workflow
        async def run_analysis(workspace_id: str):
            dag = DAGWorkflow()

            # Define nodes
            dag.add_node(DAGNode(
                id="symbols",
                execute=analyze_symbols.run,
                dependencies=[],
            ))

            dag.add_node(DAGNode(
                id="calls",
                execute=analyze_calls.run,
                dependencies=["symbols"],
            ))

            dag.add_node(DAGNode(
                id="patterns",
                execute=analyze_patterns.run,
                dependencies=["symbols", "calls"],
            ))

            # Execute (handles parallelism + dependencies)
            results = await dag.execute(workspace_id=workspace_id)

            return results
    """

    def __init__(self):
        self.nodes: Dict[str, DAGNode] = {}
        self.results: Dict[str, Any] = {}

    def add_node(self, node: DAGNode) -> None:
        """Add a node to the DAG"""
        self.nodes[node.id] = node

    def add_nodes(self, nodes: List[DAGNode]) -> None:
        """Add multiple nodes to the DAG"""
        for node in nodes:
            self.add_node(node)

    def get_execution_batches(self) -> List[List[DAGNode]]:
        """
        Get nodes grouped into batches for parallel execution.

        Returns list of batches where:
        - All nodes in a batch are independent (can run in parallel)
        - Each batch depends only on previous batches

        Example:
            [[node_a, node_b, node_c],     # Batch 1: No dependencies
             [node_d, node_e],              # Batch 2: Depend on Batch 1
             [node_f]]                      # Batch 3: Depends on Batch 1+2
        """
        # Build dependency graph
        in_degree = {node_id: 0 for node_id in self.nodes}
        graph = defaultdict(list)

        for node_id, node in self.nodes.items():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    raise ValueError(f"Node '{node_id}' depends on unknown node '{dep}'")
                graph[dep].append(node_id)
                in_degree[node_id] += 1

        # Topological sort with batching
        batches = []
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])

        while queue:
            # Current batch: all nodes with no remaining dependencies
            batch = list(queue)
            queue.clear()

            batches.append([self.nodes[node_id] for node_id in batch])

            # Process batch
            for node_id in batch:
                for neighbor in graph[node_id]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        # Check for cycles
        if len([node for batch in batches for node in batch]) != len(self.nodes):
            raise ValueError("DAG contains a cycle")

        return batches

    async def execute(
        self,
        progress_callback: Optional[Callable[[str, str], None]] = None,
        **shared_args: Any,
    ) -> Dict[str, Any]:
        """
        Execute the DAG.

        Args:
            progress_callback: Optional callback(node_id, status) for progress tracking
            **shared_args: Arguments passed to all node execute functions

        Returns:
            Dict mapping node_id -> execution result
        """
        batches = self.get_execution_batches()
        total_nodes = len(self.nodes)
        completed = 0

        for batch in batches:
            # Execute all nodes in batch concurrently
            tasks = []

            for node in batch:
                # Gather dependency results
                dependency_results = {
                    dep: self.results[dep] for dep in node.dependencies
                }

                # Create task
                task = self._execute_node(
                    node=node,
                    dependency_results=dependency_results,
                    shared_args=shared_args,
                    progress_callback=progress_callback,
                )
                tasks.append(task)

            # Wait for batch to complete
            batch_results = await asyncio.gather(*tasks)

            # Store results
            for node, result in zip(batch, batch_results):
                self.results[node.id] = result
                completed += 1

                if progress_callback:
                    progress_callback(node.id, "completed")

        return self.results

    async def _execute_node(
        self,
        node: DAGNode,
        dependency_results: Dict[str, Any],
        shared_args: Dict[str, Any],
        progress_callback: Optional[Callable],
    ) -> Any:
        """Execute a single node"""
        if progress_callback:
            progress_callback(node.id, "started")

        try:
            # Call activity with dependencies + shared args
            result = await node.execute(
                dependencies=dependency_results,
                **shared_args,
            )

            return result
        except Exception as e:
            if progress_callback:
                progress_callback(node.id, f"failed: {e}")
            raise
