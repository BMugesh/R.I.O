"""GPU Accelerated Workload Benchmarks for R.I.O. (Milestone 4)."""

import time
from typing import Any, Dict
from services.gpu.benchmark import run_matrix_benchmark


def benchmark_gpu_matrix(size: int = 1024, iterations: int = 5) -> Dict[str, Any]:
    return run_matrix_benchmark(size=size, iterations=iterations)


def benchmark_gpu_embeddings(batch_size: int = 50) -> Dict[str, Any]:
    from services.inference.embeddings import get_embedding_service
    service = get_embedding_service()
    texts = [f"This is test sample document number {i} for memory embedding" for i in range(batch_size)]

    t0 = time.perf_counter()
    _ = service._gpu_embed_kernel(texts)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return {"workload": "gpu_embeddings", "batch_size": batch_size, "latency_ms": round(elapsed_ms, 2)}


def benchmark_gpu_vision(iterations: int = 100) -> Dict[str, Any]:
    from services.inference.vision import get_vision_service
    service = get_vision_service()

    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = service._gpu_vision_kernel({"query": "search box", "image": None})
    total_ms = (time.perf_counter() - t0) * 1000.0
    avg_ms = max(0.005, total_ms / iterations)
    return {"workload": "gpu_vision", "latency_ms": round(avg_ms, 3)}


def benchmark_gpu_stt(iterations: int = 50) -> Dict[str, Any]:
    from services.inference.stt import get_stt_service
    service = get_stt_service()
    dummy_wav = b"RIFF" + b"\x00" * 32000

    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = service._gpu_stt_kernel(dummy_wav)
    total_ms = (time.perf_counter() - t0) * 1000.0
    avg_ms = max(0.005, total_ms / iterations)
    return {"workload": "gpu_stt", "latency_ms": round(avg_ms, 3)}
