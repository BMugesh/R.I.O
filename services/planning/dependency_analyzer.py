"""Dependency Analyzer for R.I.O. (Milestone 5).

Validates DAG structure, detects cycles, calculates in-degrees,
and performs topological sorting for execution ordering.
"""

from typing import Dict, List, Optional, Set, Tuple
from packages.schemas.tasks import TaskStep


class DependencyCycleError(Exception):
    """Raised when a circular dependency is detected in the plan DAG."""
    pass


class DependencyAnalyzer:
    """Analyzes dependencies among steps in a task execution graph."""

    @staticmethod
    def build_graph(steps: List[TaskStep]) -> Tuple[Dict[str, List[str]], Dict[str, int]]:
        """Build forward adjacency list and in-degree map for all steps."""
        adj: Dict[str, List[str]] = {s.id: [] for s in steps}
        in_degree: Dict[str, int] = {s.id: 0 for s in steps}

        step_ids = set(adj.keys())

        for s in steps:
            for dep in s.dependencies:
                if dep in step_ids:
                    adj[dep].append(s.id)
                    in_degree[s.id] += 1

        return adj, in_degree

    @staticmethod
    def detect_cycles(steps: List[TaskStep]) -> Optional[List[str]]:
        """Detect if there is a cycle in the task graph.

        Returns the list of node IDs forming the cycle if detected, else None.
        """
        adj: Dict[str, List[str]] = {s.id: [] for s in steps}
        for s in steps:
            for dep in s.dependencies:
                if dep in adj:
                    adj[dep].append(s.id)

        # 0: unvisited, 1: visiting (in recursion stack), 2: visited
        visited: Dict[str, int] = {s.id: 0 for s in steps}
        path: List[str] = []

        def dfs(node: str) -> Optional[List[str]]:
            visited[node] = 1
            path.append(node)
            for neighbor in adj.get(node, []):
                if visited[neighbor] == 1:
                    # Found cycle
                    cycle_start_idx = path.index(neighbor)
                    return path[cycle_start_idx:] + [neighbor]
                if visited[neighbor] == 0:
                    result = dfs(neighbor)
                    if result:
                        return result
            path.pop()
            visited[node] = 2
            return None

        for step in steps:
            if visited[step.id] == 0:
                cycle = dfs(step.id)
                if cycle:
                    return cycle
        return None

    @classmethod
    def topological_sort(cls, steps: List[TaskStep]) -> List[TaskStep]:
        """Return steps sorted in topological order according to their dependencies.

        Raises DependencyCycleError if a cycle is present.
        """
        cycle = cls.detect_cycles(steps)
        if cycle:
            raise DependencyCycleError(f"Circular dependency detected: {' -> '.join(cycle)}")

        step_map = {s.id: s for s in steps}
        adj, in_degree = cls.build_graph(steps)

        # Queue of nodes with 0 in-degree (ready to execute)
        ready = [sid for sid, deg in in_degree.items() if deg == 0]
        ordered: List[TaskStep] = []

        while ready:
            curr_id = ready.pop(0)
            ordered.append(step_map[curr_id])
            for succ in adj.get(curr_id, []):
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    ready.append(succ)

        if len(ordered) != len(steps):
            raise DependencyCycleError("Graph contains unreachable or cyclic steps")

        return ordered
