"""Unit and Integration Tests for Universal Windows Application Control.

Validates:
1. Dynamic multi-source application discovery (Start Menu, UWP/Get-StartApps, Registry, PATH).
2. Interactive desktop window enumeration (OpenInputDesktop + EnumDesktopWindows).
3. Universal window lifecycle controls (launch, focus, minimize, maximize, close, read, status).
4. Strict security boundary against password managers and credential vaults.
5. Permission mappings for all application capabilities.
6. DAG Planner multi-step task decomposition (VS Code, Spotify, File Explorer, lifecycle).
7. Conversational intent classification and response generation for universal apps.
"""

import platform
import pytest
from unittest.mock import MagicMock, patch

from packages.schemas.agents import AgentStatus
from agents.computer.agent import ComputerAgent
from runtime.app_controller import UniversalAppController, AppInfo, WindowInfo
from runtime.permissions import PermissionManager, Capability
from packages.schemas.input import RIOInput
from runtime.validator import WindowsAppValidator
from services.conversation.context import ConversationContext
from services.conversation.intent import IntentClassifier, IntentType
from services.conversation.response import ResponseGenerator
from services.orchestrator.dag_planner import DAGPlanner


# =====================================================================
# 1. Dynamic Discovery & Resolution Tests
# =====================================================================

def test_dynamic_discovery_populated():
    """Verify that dynamic discovery discovers installed applications without a hardcoded whitelist."""
    apps = UniversalAppController.discover_all_apps()
    assert isinstance(apps, dict)
    assert len(apps) > 0, "Expected at least one installed application to be discovered on Windows."
    
    # Verify every discovered item is an AppInfo instance
    for key, info in list(apps.items())[:10]:
        assert isinstance(info, AppInfo)
        assert info.app_key == key
        assert info.display_name


def test_resolve_standard_desktop_app():
    """Verify resolution of standard desktop apps (e.g. Notepad, Explorer, cmd)."""
    info = UniversalAppController.resolve_app("notepad")
    assert isinstance(info, AppInfo)
    assert info.installed is True
    assert info.executable_path or info.aumid or info.protocol


def test_resolve_uwp_app():
    """Verify resolution of UWP / Windows Store packaged apps (e.g. Calculator, WhatsApp)."""
    calc_info = UniversalAppController.resolve_app("calculator")
    assert isinstance(calc_info, AppInfo)
    assert calc_info.installed is True
    # Calculator on Windows 10/11 has an AUMID or protocol
    assert calc_info.aumid or calc_info.protocol or calc_info.executable_path


def test_resolve_unknown_application():
    """Verify resolution of completely unknown applications safely returns installed=False."""
    unknown = UniversalAppController.resolve_app("definitely_nonexistent_application_xyz_999")
    assert isinstance(unknown, AppInfo)
    assert unknown.installed is False
    assert unknown.executable_path is None
    assert unknown.aumid is None


def test_validator_delegates_to_universal_controller():
    """Ensure WindowsAppValidator.discover_app seamlessly integrates with UniversalAppController."""
    res = WindowsAppValidator.discover_app("calculator")
    assert res["app_key"] == "calculator"
    assert res["installed"] is True
    assert res["display_name"]


# =====================================================================
# 2. Interactive Desktop Window Enumeration Tests
# =====================================================================

def test_enumerate_windows_interactive_desktop():
    """Verify enumerate_windows returns active desktop windows with valid metadata."""
    if platform.system() == "Windows":
        windows = UniversalAppController.enumerate_windows(visible_only=True)
        assert isinstance(windows, list)
        assert len(windows) > 0, "Expected to find at least one window on active desktop."
        
        first = windows[0]
        assert isinstance(first, WindowInfo)
        assert first.hwnd > 0
        assert first.title
        assert first.pid > 0


def test_find_window_for_app_matching():
    """Verify matching logic for finding application window by name or process."""
    if platform.system() == "Windows":
        # Explorer is always running on Windows interactive sessions
        win = UniversalAppController.find_window_for_app("explorer")
        if win:
            assert isinstance(win, WindowInfo)
            assert win.hwnd > 0


# =====================================================================
# 3. Universal Window Status & Read Tests
# =====================================================================

def test_get_app_status():
    """Verify get_status returns structured application status."""
    st = UniversalAppController.get_status("definitely_nonexistent_xyz")
    assert st["app"].lower() == "definitely_nonexistent_xyz"
    assert st["installed"] is False
    assert st["running"] is False
    assert st["has_window"] is False


def test_read_window_structure():
    """Verify read_window produces expected structured inspection dictionary."""
    read_data = UniversalAppController.read_window("nonexistent_fake_app")
    assert "app" in read_data
    assert read_data["found"] is False


# =====================================================================
# 4. Universal Window Control Lifecycle Tests
# =====================================================================

def test_window_control_nonexistent_fails_safely():
    """Verify control actions on non-existent apps fail gracefully with error messages."""
    ok_foc, msg_foc = UniversalAppController.focus("nonexistent_fake_app_123")
    assert ok_foc is False
    assert "not found" in msg_foc.lower()

    ok_min, msg_min = UniversalAppController.minimize("nonexistent_fake_app_123")
    assert ok_min is False
    assert "not found" in msg_min.lower()

    ok_max, msg_max = UniversalAppController.maximize("nonexistent_fake_app_123")
    assert ok_max is False
    assert "not found" in msg_max.lower()

    ok_cls, msg_cls = UniversalAppController.close("nonexistent_fake_app_123")
    assert ok_cls is False
    assert "not open" in msg_cls.lower() or "not found" in msg_cls.lower()


# =====================================================================
# 5. Security Boundary & Permission Tests
# =====================================================================

@pytest.mark.parametrize("protected_app", [
    "1password", "bitwarden", "keepass", "lastpass", "dashlane",
    "authenticator", "credential manager", "windows credential vault",
])
def test_security_boundary_blocks_credential_vaults(protected_app):
    """Verify UniversalAppController and PermissionManager strictly block password managers."""
    assert UniversalAppController.is_protected(protected_app) is True

    pm = PermissionManager()
    assert pm.is_protected_target(protected_app) is True


@pytest.mark.parametrize("safe_app", [
    "chrome", "whatsapp", "calculator", "spotify", "vs code", "discord", "photoshop", "notepad"
])
def test_security_boundary_permits_general_apps(safe_app):
    """Verify standard productivity/media apps are not marked as protected."""
    assert UniversalAppController.is_protected(safe_app) is False


@pytest.mark.asyncio
async def test_computer_agent_enforces_security_boundary():
    """Verify ComputerAgent strictly rejects any action targeted at protected credential vaults."""
    agent = ComputerAgent()
    input_data = RIOInput(
        id="test-sec-1",
        payload={"action_type": "open_application", "app_name": "Bitwarden"},
    )
    res = await agent.run(input_data, context={})
    assert res.status == AgentStatus.FAILED
    assert "restricted by security policy" in res.message
    assert res.data.get("error") == "security_boundary_violation"


def test_permissions_mapping_for_application_actions():
    """Verify PermissionManager correctly maps all universal application action strings."""
    pm = PermissionManager()
    actions_to_check = [
        ("application.launch", Capability.APPLICATION_LAUNCH),
        ("application.close", Capability.APPLICATION_CLOSE),
        ("application.focus", Capability.APPLICATION_FOCUS),
        ("application.minimize", Capability.APPLICATION_CONTROL),
        ("application.maximize", Capability.APPLICATION_CONTROL),
        ("application.switch", Capability.APPLICATION_CONTROL),
        ("application.status", "status"),
        ("application.discover", "status"),
        ("application.resolve", "status"),
        ("application.window.read", Capability.SCREEN_READ),
        ("application.input", Capability.KEYBOARD_CONTROL),
        ("application.control", Capability.APPLICATION_CONTROL),
    ]
    for action, expected_cap in actions_to_check:
        allowed, cap = pm.is_action_allowed(action)
        assert cap == expected_cap, f"Expected {action} to map to {expected_cap}, got {cap}"


# =====================================================================
# 6. ComputerAgent Universal Action Execution Tests
# =====================================================================

@pytest.mark.asyncio
async def test_computer_agent_status_and_read_actions():
    """Verify ComputerAgent executes application.status and application.window.read."""
    agent = ComputerAgent()

    # application.status
    input_status = RIOInput(
        id="test-stat-1",
        payload={"action_type": "application.status", "app_name": "nonexistent_app"},
    )
    res_stat = await agent.run(input_status, context={})
    assert res_stat.status == AgentStatus.SUCCESS
    assert "status_info" in res_stat.data

    # application.window.read
    input_read = RIOInput(
        id="test-read-1",
        payload={"action_type": "application.window.read", "app_name": "nonexistent_app"},
    )
    res_read = await agent.run(input_read, context={})
    assert res_read.status == AgentStatus.SUCCESS
    assert "window_data" in res_read.data

    # application.discover
    input_disc = RIOInput(
        id="test-disc-1",
        payload={"action_type": "application.discover", "app_name": "calculator"},
    )
    res_disc = await agent.run(input_disc, context={})
    assert res_disc.status == AgentStatus.SUCCESS
    assert res_disc.data.get("installed") is True


# =====================================================================
# 7. DAG Planner Decomposition & Routing Tests
# =====================================================================

@pytest.mark.asyncio
async def test_dag_planner_generic_app_launch():
    """Verify DAGPlanner generates launch and verification steps for any generic app."""
    planner = DAGPlanner()
    plan = await planner.create_plan("Open WhatsApp", context={})
    assert len(plan.steps) == 2
    assert plan.steps[0].action.action_type == "open_application"
    assert plan.steps[0].action.parameters["app_name"].lower() == "whatsapp"
    assert plan.steps[1].action.action_type == "verify_app_state"


@pytest.mark.asyncio
async def test_dag_planner_app_lifecycle_controls():
    """Verify DAGPlanner creates proper single-step plans for close, minimize, maximize, focus, status."""
    planner = DAGPlanner()

    # Close
    p_close = await planner.create_plan("Close Spotify", context={})
    assert len(p_close.steps) == 1
    assert p_close.steps[0].action.action_type == "close_application"
    assert p_close.steps[0].action.parameters["app_name"].lower() == "spotify"

    # Minimize
    p_min = await planner.create_plan("Minimize Chrome", context={})
    assert len(p_min.steps) == 1
    assert p_min.steps[0].action.action_type == "application.minimize"
    assert p_min.steps[0].action.parameters["app_name"].lower() == "chrome"

    # Maximize
    p_max = await planner.create_plan("Maximize Discord", context={})
    assert len(p_max.steps) == 1
    assert p_max.steps[0].action.action_type == "application.maximize"
    assert p_max.steps[0].action.parameters["app_name"].lower() == "discord"

    # Focus
    p_foc = await planner.create_plan("Focus VS Code", context={})
    assert len(p_foc.steps) == 1
    assert p_foc.steps[0].action.action_type == "application.focus"
    assert p_foc.steps[0].action.parameters["app_name"].lower() == "vs code"

    # Status
    p_stat = await planner.create_plan("Status of Calculator", context={})
    assert len(p_stat.steps) == 1
    assert p_stat.steps[0].action.action_type == "application.status"
    assert p_stat.steps[0].action.parameters["app_name"].lower() == "calculator"


@pytest.mark.asyncio
async def test_dag_planner_multi_step_compound_workflows():
    """Verify multi-step decompositions for compound application tasks."""
    planner = DAGPlanner()

    # VS Code + project + test suite
    p_vscode = await planner.create_plan("Open VS Code and run tests on my project", context={})
    assert len(p_vscode.steps) == 3
    assert p_vscode.steps[0].action.action_type == "open_application"
    assert p_vscode.steps[1].action.action_type == "run_tests"
    assert p_vscode.steps[2].action.action_type == "verify_file"

    # Spotify search and play
    p_spot = await planner.create_plan("Play Bohemian Rhapsody on Spotify", context={})
    assert len(p_spot.steps) == 3
    assert p_spot.steps[0].action.action_type == "open_application"
    assert p_spot.steps[1].action.action_type == "application.control"
    assert p_spot.steps[2].action.action_type == "verify_app_state"

    # File Explorer navigation
    p_exp = await planner.create_plan("Open my project folder in File Explorer", context={})
    assert len(p_exp.steps) == 2
    assert p_exp.steps[0].action.action_type == "open_application"
    assert p_exp.steps[1].action.action_type == "verify_app_state"


# =====================================================================
# 8. Conversational Intent & Response Formatting Tests
# =====================================================================

def test_intent_classification_app_lifecycle():
    """Verify IntentClassifier classifies lifecycle and status utterances as actions."""
    # Close
    itype, contract = IntentClassifier.classify("Close WhatsApp")
    assert itype == IntentType.ACTION
    assert contract.goal == "Close WhatsApp"

    # Minimize
    itype, contract = IntentClassifier.classify("Minimize Spotify")
    assert itype == IntentType.ACTION

    # Maximize
    itype, contract = IntentClassifier.classify("Maximize Discord")
    assert itype == IntentType.ACTION

    # Focus
    itype, contract = IntentClassifier.classify("Focus Chrome")
    assert itype == IntentType.ACTION

    # Status
    itype, contract = IntentClassifier.classify("Is Calculator running?")
    assert itype == IntentType.ACTION
    assert contract.action_type == "application.status"
    assert contract.parameters.get("app_name").lower() == "calculator"


def test_intent_follow_up_resolution_for_apps():
    """Verify pronoun follow-ups resolve against active conversation context."""
    ctx = ConversationContext(last_action_target="Spotify")
    resolved = IntentClassifier.resolve_follow_ups("Close it", ctx)
    assert resolved == "Close Spotify"

    resolved_min = IntentClassifier.resolve_follow_ups("Minimize it", ctx)
    assert resolved_min == "Minimize Spotify"


def test_response_generator_universal_apps():
    """Verify ResponseGenerator synthesizes concise, verified responses for any application."""
    # Open
    assert ResponseGenerator.format_action_response("open whatsapp", success=True, verified=True) == "Whatsapp is open."
    assert ResponseGenerator.format_action_response("launch photoshop", success=True, verified=True) == "Photoshop is open."
    assert ResponseGenerator.format_action_response("open vs code", success=True, verified=True) == "VS Code is open."

    # Close
    assert ResponseGenerator.format_action_response("close spotify", success=True, verified=True) == "Spotify is closed."

    # Minimize
    assert ResponseGenerator.format_action_response("minimize chrome", success=True, verified=True) == "Chrome is minimized."

    # Maximize
    assert ResponseGenerator.format_action_response("maximize discord", success=True, verified=True) == "Discord is maximized."

    # Focus
    assert ResponseGenerator.format_action_response("focus vscode", success=True, verified=True) == "Switched to Vscode."

    # Status Query with Evidence
    ev_running = {"data": {"status_info": {"running": True, "display_name": "Calculator"}}}
    resp_running = ResponseGenerator.format_action_response("is calculator running?", success=True, verified=True, evidence=ev_running)
    assert resp_running == "Yes, Calculator is running."

    ev_stopped = {"data": {"status_info": {"running": False, "display_name": "Calculator"}}}
    resp_stopped = ResponseGenerator.format_action_response("is calculator running?", success=True, verified=True, evidence=ev_stopped)
    assert resp_stopped == "No, Calculator is not running."
