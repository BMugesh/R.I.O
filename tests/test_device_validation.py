"""Unit and Integration Tests for Windows Application Validator (Milestone 2.5)."""
import pytest
pytestmark = pytest.mark.hardware



import platform
import pytest
from runtime.validator import AppValidationResult, WindowsAppValidator, KNOWN_APPS


def test_validator_app_discovery_known_apps():
    # Notepad discovery (available on standard Windows OS)
    notepad_spec = WindowsAppValidator.discover_app("notepad")
    assert notepad_spec["app_key"] == "notepad"
    assert notepad_spec["display_name"] == "Notepad"
    if platform.system() == "Windows":
        assert notepad_spec["installed"] is True
        assert notepad_spec["executable_path"] is not None

    # Chrome discovery structure
    chrome_spec = WindowsAppValidator.discover_app("chrome")
    assert chrome_spec["app_key"] == "chrome"
    assert chrome_spec["display_name"] == "Google Chrome"

    # Non-existent app discovery
    non_existent = WindowsAppValidator.discover_app("some_fake_nonexistent_application_xyz")
    assert non_existent["installed"] is False
    assert non_existent["executable_path"] is None


@pytest.mark.asyncio
async def test_validator_nonexistent_app_reporting():
    res = await WindowsAppValidator.validate_application(
        "nonexistent_dummy_app_xyz",
        close_after=True,
    )
    assert isinstance(res, AppValidationResult)
    assert res.status == "NOT FOUND"
    assert res.installed is False
    assert res.error_message is not None


@pytest.mark.asyncio
async def test_validator_notepad_layered_execution():
    if platform.system() == "Windows":
        res = await WindowsAppValidator.validate_application("notepad", close_after=True, verification_timeout=3.0)
        assert res.installed is True
        assert res.status in ("VERIFIED", "UNCERTAIN")
        assert res.pid is not None
        if res.status == "VERIFIED":
            assert res.window_handle is not None
            assert res.window_title is not None
            assert res.verification_layer == "full_layered"


@pytest.mark.asyncio
async def test_validator_matrix_execution():
    target_apps = ["notepad", "nonexistent_fake_app_999"]
    results = await WindowsAppValidator.run_matrix_test(target_apps, close_after=True)
    assert len(results) == 2

    # First app is notepad
    assert results[0].app_key == "notepad"
    # Second app is fake app
    assert results[1].status == "NOT FOUND"
