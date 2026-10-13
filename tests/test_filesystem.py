"""Unit tests for FileSystemAgent with truthful verification and security policies."""

import pytest
from pathlib import Path
from agents.filesystem.agent import FileSystemAgent
from packages.schemas.agents import AgentStatus
from packages.schemas.input import InputType, RIOInput

pytestmark = pytest.mark.unit

@pytest.fixture
def fs_agent():
    return FileSystemAgent()

def test_filesystem_manifest(fs_agent):
    manifest = fs_agent.manifest
    assert manifest.id == "filesystem_agent"
    assert "read_file" in manifest.capabilities
    assert "write_file" in manifest.capabilities
    assert "list_files" in manifest.capabilities
    assert "filesystem.read_file" in manifest.required_tools
    assert "filesystem.write_file" in manifest.required_tools

@pytest.mark.asyncio
async def test_filesystem_write_and_read(fs_agent, tmp_path):
    target_file = tmp_path / "test_data.txt"
    content_str = "Hello R.I.O. verified storage!"

    # 1. Write file
    res_write = await fs_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "filesystem.write_file", "path": str(target_file), "content": content_str}),
        context={}
    )
    assert res_write.status == AgentStatus.SUCCESS
    assert res_write.data["verified"] is True
    assert res_write.data["sha256"] is not None
    assert target_file.exists()
    assert target_file.read_text(encoding="utf-8") == content_str

    # 2. Read file
    res_read = await fs_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "filesystem.read_file", "path": str(target_file)}),
        context={}
    )
    assert res_read.status == AgentStatus.SUCCESS
    assert res_read.data["verified"] is True
    assert res_read.data["content"] == content_str
    assert res_read.data["size_bytes"] == len(content_str.encode("utf-8"))

@pytest.mark.asyncio
async def test_filesystem_list_and_metadata(fs_agent, tmp_path):
    sub = tmp_path / "sub_dir"
    sub.mkdir()
    f1 = sub / "sample.json"
    f1.write_text('{"key": "value"}', encoding="utf-8")

    # 1. List dir
    res_list = await fs_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "filesystem.list_dir", "path": str(sub)}),
        context={}
    )
    assert res_list.status == AgentStatus.SUCCESS
    assert res_list.data["verified"] is True
    assert res_list.data["count"] == 1
    assert res_list.data["entries"][0]["name"] == "sample.json"

    # 2. Metadata
    res_meta = await fs_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "filesystem.get_metadata", "path": str(f1)}),
        context={}
    )
    assert res_meta.status == AgentStatus.SUCCESS
    assert res_meta.data["verified"] is True
    assert res_meta.data["is_file"] is True
    assert res_meta.data["sha256"] is not None

@pytest.mark.asyncio
async def test_filesystem_copy_move_and_delete(fs_agent, tmp_path):
    src = tmp_path / "source.txt"
    src.write_text("moveable content", encoding="utf-8")
    copied = tmp_path / "copied.txt"
    moved = tmp_path / "moved.txt"

    # 1. Copy
    res_copy = await fs_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "filesystem.copy_file", "path": str(src), "destination": str(copied)}),
        context={}
    )
    assert res_copy.status == AgentStatus.SUCCESS
    assert src.exists()
    assert copied.exists()

    # 2. Move
    res_move = await fs_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "filesystem.move_file", "path": str(copied), "destination": str(moved)}),
        context={}
    )
    assert res_move.status == AgentStatus.SUCCESS
    assert not copied.exists()
    assert moved.exists()

    # 3. Delete
    res_del = await fs_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "filesystem.delete_file", "path": str(moved)}),
        context={}
    )
    assert res_del.status == AgentStatus.SUCCESS
    assert not moved.exists()

@pytest.mark.asyncio
async def test_filesystem_security_boundary_enforcement(fs_agent, tmp_path):
    # Prohibited files: .env, id_rsa, secrets.json
    for bad_name in (".env", "id_rsa", "secrets.json"):
        res = await fs_agent.run(
            RIOInput(type=InputType.TEXT, payload={"action": "filesystem.read_file", "path": str(tmp_path / bad_name)}),
            context={}
        )
        assert res.status == AgentStatus.FAILED
        assert res.data["verified"] is False
        assert res.data["error"] == "security_policy_violation"

@pytest.mark.asyncio
async def test_filesystem_truthful_failure_on_missing_file(fs_agent, tmp_path):
    # Non-existent file must fail with verified=False (NO FAKE SUCCESS)
    missing = tmp_path / "does_not_exist_xyz.txt"
    res = await fs_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "filesystem.read_file", "path": str(missing)}),
        context={}
    )
    assert res.status == AgentStatus.FAILED
    assert res.data["verified"] is False
    assert res.data["exists"] is False
