"""Test Local Embedding Service and GPU acceleration (Milestone 4)."""

import math
import pytest
from services.inference.embeddings import EmbeddingService, get_embedding_service


@pytest.mark.asyncio
async def test_single_embedding():
    service = get_embedding_service()
    vector = await service.embed_single("Hello R.I.O. memory")

    assert len(vector) == service.dimension
    # Check normalized L2 norm ~ 1.0
    norm = math.sqrt(sum(x * x for x in vector))
    assert abs(norm - 1.0) < 0.05


@pytest.mark.asyncio
async def test_batch_embedding():
    service = get_embedding_service()
    texts = ["First query", "Second query", "Third query"]
    vectors = await service.embed(texts)

    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == service.dimension


@pytest.mark.asyncio
async def test_embedding_determinism():
    service = get_embedding_service()
    v1 = await service.embed_single("Consistent query")
    v2 = await service.embed_single("Consistent query")

    assert v1 == v2
