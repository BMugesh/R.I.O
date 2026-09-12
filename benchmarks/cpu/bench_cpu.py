"""CPU Workload Benchmarks for R.I.O. (Milestone 4)."""

import time
from typing import Any, Dict
import numpy as np


def benchmark_cpu_matrix(size: int = 1024, iterations: int = 5) -> Dict[str, Any]:
    A = np.random.randn(size, size).astype(np.float32)
    B = np.random.randn(size, size).astype(np.float32)

    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        _ = np.dot(A, B)
        times.append((time.perf_counter() - t0) * 1000.0)

    avg_ms = float(np.mean(times))
    return {"workload": "cpu_matrix", "size": f"{size}x{size}", "latency_ms": round(avg_ms, 2)}


def benchmark_cpu_embeddings(batch_size: int = 50) -> Dict[str, Any]:
    from services.inference.embeddings import get_embedding_service
    service = get_embedding_service()
    texts = [f"This is test sample document number {i} for memory embedding" for i in range(batch_size)]

    t0 = time.perf_counter()
    _ = service._cpu_embed_kernel(texts)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return {"workload": "cpu_embeddings", "batch_size": batch_size, "latency_ms": round(elapsed_ms, 2)}


def benchmark_cpu_vision(iterations: int = 100) -> Dict[str, Any]:
    from services.inference.vision import get_vision_service
    service = get_vision_service()

    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = service._cpu_vision_kernel({"query": "search box", "image": None})
    total_ms = (time.perf_counter() - t0) * 1000.0
    avg_ms = max(0.01, total_ms / iterations)
    return {"workload": "cpu_vision", "latency_ms": round(avg_ms, 3)}


def benchmark_cpu_stt(iterations: int = 50) -> Dict[str, Any]:
    from services.inference.stt import get_stt_service
    service = get_stt_service()
    dummy_wav = b"RIFF" + b"\x00" * 32000  # 1 sec audio

    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = service._cpu_stt_kernel(dummy_wav)
    total_ms = (time.perf_counter() - t0) * 1000.0
    avg_ms = max(0.01, total_ms / iterations)
    return {"workload": "cpu_stt", "latency_ms": round(avg_ms, 3)}
