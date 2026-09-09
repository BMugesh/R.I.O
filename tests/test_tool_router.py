"""Unit tests for Tool Router and Built-in tools."""

import os
import pytest
from packages.schemas.tools import ToolCall
from services.tool_router.registry import ToolRegistry


@pytest.mark.asyncio
async def test_builtin_datetime_tool():
    registry = ToolRegistry()
    call = ToolCall(id="call_1", tool_id="builtin_get_datetime", arguments={})
    res = await registry.execute(call)
    assert res.success is True
    assert "current_datetime" in res.output


@pytest.mark.asyncio
async def test_builtin_math_tool():
    registry = ToolRegistry()
    call = ToolCall(id="call_2", tool_id="builtin_math_eval", arguments={"expression": "10 * 5 + 2"})
    res = await registry.execute(call)
    assert res.success is True
    assert res.output["result"] == 52


@pytest.mark.asyncio
async def test_builtin_file_read_write(tmp_path):
    registry = ToolRegistry()
    test_file = str(tmp_path / "test_rio.txt")

    # Write
    write_call = ToolCall(id="call_w", tool_id="builtin_write_file", arguments={"path": test_file, "content": "Hello RIO"})
    w_res = await registry.execute(write_call)
    assert w_res.success is True

    # Read
    read_call = ToolCall(id="call_r", tool_id="builtin_read_file", arguments={"path": test_file})
    r_res = await registry.execute(read_call)
    assert r_res.success is True
    assert r_res.output["content"] == "Hello RIO"
