"""Worker and model registry for R.I.O. compute fabric."""

from typing import Any, Callable, Dict, List, Optional


class ComputeRegistry:
    """Registry maintaining references to workers and hardware adapters."""

    def __init__(self):
        self._workers: Dict[str, Dict[str, Callable[[Any], Any]]] = {
            "cpu": {},
            "gpu": {},
            "remote": {},
        }

    def register(self, target: str, workload_type: str, handler: Callable[[Any], Any]) -> None:
        if target in self._workers:
            self._workers[target][workload_type] = handler

    def get_worker(self, target: str, workload_type: str) -> Optional[Callable[[Any], Any]]:
        return self._workers.get(target, {}).get(workload_type)

    def list_capabilities(self) -> Dict[str, List[str]]:
        return {k: list(v.keys()) for k, v in self._workers.items()}
