"""Pytest Configuration and Test Resource Governor Hooks (Milestone 4.5).

Provides automatic test environment sandboxing (RIO_ENV=test),
session and per-test resource tracking, safe fixtures, and leak detection.
"""

import os
import pytest
from typing import Generator

# Ensure test environment mode is active before any other R.I.O. modules import
os.environ["RIO_ENV"] = "test"
os.environ.setdefault("DEFAULT_MODEL_PROVIDER", "mock")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from services.compute.gpu_executor import GPUExecutor
from services.model_router.router import ModelRouter
from services.test_governor.governor import TestResourceGovernor, get_test_governor


def pytest_configure(config):
    """Session startup: initialize Test Resource Governor and start baseline snapshot."""
    gov = get_test_governor()
    gov.start_session()


def pytest_runtest_setup(item):
    """Pre-test hook: verify RAM/VRAM safety headroom and capture test baseline."""
    gov = get_test_governor()
    markers = [m.name for m in item.iter_markers()]
    gov.on_test_start(test_name=item.nodeid, markers=markers)


def pytest_runtest_teardown(item):
    """Post-test hook: execute resource cleanup dispatcher and evaluate leak diff."""
    gov = get_test_governor()
    markers = [m.name for m in item.iter_markers()]
    gov.on_test_end(test_name=item.nodeid, markers=markers)


def pytest_sessionfinish(session, exitstatus):
    """Session end: generate persistence report and output terminal summary table."""
    gov = get_test_governor()
    
    total = session.testscollected
    failed = session.testsfailed
    passed = total - failed

    terminal_report = gov.finish_session(
        total_tests=total,
        passed_tests=passed,
        failed_tests=failed,
    )
    # Output report to terminal
    print("\n" + terminal_report + "\n")


@pytest.fixture
def governor() -> TestResourceGovernor:
    """Fixture providing direct access to the active TestResourceGovernor."""
    return get_test_governor()


@pytest.fixture(scope="session")
def session_gpu_executor() -> Generator[GPUExecutor, None, None]:
    """Session-scoped GPU executor with lazy loading and deterministic teardown."""
    executor = GPUExecutor()
    yield executor
    executor.shutdown()


@pytest.fixture
def mock_model_router() -> ModelRouter:
    """Fast, local mock ModelRouter for isolated unit tests."""
    return ModelRouter(default_provider="mock")
