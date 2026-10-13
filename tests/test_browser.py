"""Tests for BrowserAgent with real Playwright execution and truthful verification."""

import os
import pytest
from pathlib import Path
from agents.browser.agent import BrowserAgent
from packages.schemas.agents import AgentStatus
from packages.schemas.input import InputType, RIOInput
from services.model_router.router import ModelRouter

@pytest.fixture
async def browser_agent():
    agent = BrowserAgent(model_router=ModelRouter(default_provider="mock"))
    yield agent
    await agent.close()

@pytest.mark.asyncio
async def test_browser_manifest(browser_agent):
    manifest = browser_agent.manifest
    assert manifest.id == "browser_agent"
    assert "web_navigation" in manifest.capabilities
    assert "browser.navigate" in manifest.required_tools
    assert "browser.screenshot" in manifest.required_tools

@pytest.mark.asyncio
async def test_browser_navigate_and_read_dom(browser_agent):
    html = "data:text/html,<html><head><title>RIO Playwright Unit Test</title></head><body><h1 id='headline'>Real DOM Execution</h1><p id='desc'>BrowserAgent works</p></body></html>"
    
    # 1. Navigate
    res_nav = await browser_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "browser.navigate", "url": html, "headless": True}),
        context={}
    )
    assert res_nav.status == AgentStatus.SUCCESS
    assert res_nav.data["verified"] is True
    assert res_nav.data["page_title"] == "RIO Playwright Unit Test"
    assert res_nav.evidence[0].verified is True
    assert res_nav.evidence[0].source == "playwright"

    # 2. Read Title
    res_title = await browser_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "browser.read_title"}),
        context={}
    )
    assert res_title.status == AgentStatus.SUCCESS
    assert res_title.data["title"] == "RIO Playwright Unit Test"

    # 3. Read DOM
    res_dom = await browser_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "browser.read_dom", "selector": "#headline"}),
        context={}
    )
    assert res_dom.status == AgentStatus.SUCCESS
    assert res_dom.data["content"] == "Real DOM Execution"
    assert res_dom.data["verified"] is True

@pytest.mark.asyncio
async def test_browser_find_element_truthfulness(browser_agent):
    html = "data:text/html,<html><body><button id='submit-btn'>Click Me</button></body></html>"
    await browser_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "browser.navigate", "url": html, "headless": True}),
        context={}
    )

    # Existing element -> verified True
    res_found = await browser_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "browser.find", "selector": "#submit-btn"}),
        context={}
    )
    assert res_found.status == AgentStatus.SUCCESS
    assert res_found.data["found"] is True
    assert res_found.data["verified"] is True

    # Missing element -> verified False, status FAILED (NO FAKE SUCCESS)
    res_missing = await browser_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "browser.find", "selector": "#non-existent-button-xyz"}),
        context={}
    )
    assert res_missing.status == AgentStatus.FAILED
    assert res_missing.data["found"] is False
    assert res_missing.data["verified"] is False

@pytest.mark.asyncio
async def test_browser_click_type_and_eval(browser_agent):
    html = """data:text/html,
    <html>
      <body>
        <input id="user-input" type="text" />
        <button id="trigger" onclick="document.getElementById('result').innerText = document.getElementById('user-input').value">Submit</button>
        <div id="result">Initial</div>
      </body>
    </html>"""
    await browser_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "browser.navigate", "url": html, "headless": True}),
        context={}
    )

    # Type text
    res_type = await browser_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "browser.type", "selector": "#user-input", "text": "Autonomous RIO"}),
        context={}
    )
    assert res_type.status == AgentStatus.SUCCESS
    assert res_type.data["verified"] is True

    # Click button
    res_click = await browser_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "browser.click", "selector": "#trigger"}),
        context={}
    )
    assert res_click.status == AgentStatus.SUCCESS

    # Evaluate JS to verify DOM state
    res_eval = await browser_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "browser.evaluate", "script": "document.getElementById('result').innerText"}),
        context={}
    )
    assert res_eval.status == AgentStatus.SUCCESS
    assert res_eval.data["result"] == "Autonomous RIO"

@pytest.mark.asyncio
async def test_browser_screenshot_creates_real_file(browser_agent, tmp_path):
    html = "data:text/html,<html><body><h1 style='color:green;'>Screenshot Test</h1></body></html>"
    await browser_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "browser.navigate", "url": html, "headless": True}),
        context={}
    )

    shot_path = tmp_path / "browser_test.png"
    res_shot = await browser_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "browser.screenshot", "path": str(shot_path)}),
        context={}
    )
    assert res_shot.status == AgentStatus.SUCCESS
    assert res_shot.data["verified"] is True
    assert shot_path.exists()
    assert shot_path.stat().st_size > 0
