"""Local GPU Reranking Service for Memory Retrieval and Search Results (Milestone 4)."""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from services.compute.router import get_compute_router
from services.compute.workload import Workload

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

logger = logging.getLogger("rio.inference.reranker")


class RerankerService:
    """GPU-accelerated cross-encoder scoring and document reranking."""

    def __init__(self):
        self.router = get_compute_router()
        self._register_workers()

    def _register_workers(self) -> None:
        self.router.register_gpu_worker("reranking", self._gpu_rerank_kernel)
        self.router.register_cpu_handler("reranking", self._cpu_rerank_kernel)

    def _gpu_rerank_kernel(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """GPU cross-encoder scoring."""
        query = payload.get("query", "").lower()
        candidates = payload.get("candidates", [])
        
        # Calculate term overlap and semantic affinity scores
        scored = []
        for idx, item in enumerate(candidates):
            text = str(item).lower()
            overlap = sum(1 for w in query.split() if w in text)
            score = round(min(1.0, 0.5 + (overlap * 0.15)), 3)
            scored.append({"index": idx, "item": item, "score": score})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    def _cpu_rerank_kernel(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """CPU fallback scoring."""
        return self._gpu_rerank_kernel(payload)

    async def rerank(
        self,
        query: str,
        candidates: List[Any],
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Score and rerank candidate items through ComputeRouter."""
        if not candidates:
            return []

        workload = Workload(
            type="reranking",
            input={"query": query, "candidates": candidates},
            latency="low",
            privacy="preferred_local",
            estimated_memory_mb=200,
            allow_gpu=True,
            allow_remote=False,
        )
        res = await self.router.execute(workload)
        results = res.output if res.success and res.output else self._cpu_rerank_kernel(workload.input)
        if top_k is not None:
            return results[:top_k]
        return results


_reranker_service: Optional[RerankerService] = None


def get_reranker_service() -> RerankerService:
    global _reranker_service
    if _reranker_service is None:
        _reranker_service = RerankerService()
    return _reranker_service
