"""Test GPU Vision Inference Service (Milestone 4)."""
import pytest
pytestmark = pytest.mark.gpu



import pytest
from services.inference.vision import VisionInferenceService, get_vision_service


@pytest.mark.asyncio
async def test_vision_find_search_box():
    service = get_vision_service()
    res = await service.find_element("search box")

    assert "elements" in res
    elements = res["elements"]
    assert len(elements) > 0

    first = elements[0]
    assert first["label"] == "search_input"
    assert "box" in first
    assert "center" in first
    assert first["confidence"] > 0.8


@pytest.mark.asyncio
async def test_vision_find_chrome_icon():
    service = get_vision_service()
    res = await service.find_element("open chrome")

    assert "elements" in res
    elements = res["elements"]
    assert any("chrome" in e["label"] for e in elements)


@pytest.mark.asyncio
async def test_vision_custom_element():
    service = get_vision_service()
    res = await service.find_element("custom_widget")

    assert len(res["elements"]) > 0
    assert res["elements"][0]["label"] == "custom_widget"
