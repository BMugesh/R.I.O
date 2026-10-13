"""Unit tests for R.I.O. M5.6 Failure Recovery & Replanning."""

import pytest
pytestmark = [pytest.mark.unit, pytest.mark.recovery]

from packages.schemas.agents import Action
from packages.schemas.tasks import StepStatus, Task, TaskPlan, TaskStep
from services.recovery.classifier import FailureClassifier, FailureType
from services.recovery.fallback import FallbackManager
from services.recovery.replanner import Replanner
from services.recovery.retry_policy import RetryPolicy


def test_failure_classifier_categories():
    assert FailureClassifier.classify("Connection timed out after 30s") == FailureType.TRANSIENT
    assert FailureClassifier.classify("CUDA error: out of memory allocating 2GB") == FailureType.RESOURCE
    assert FailureClassifier.classify("HTTP 403 Forbidden: Permission denied") == FailureType.AUTHORIZATION
    assert FailureClassifier.classify("ConnectionRefusedError: [Errno 111]") == FailureType.NETWORK
    assert FailureClassifier.classify("Step verification failed: file not found") == FailureType.VERIFICATION


def test_retry_policy_rules():
    policy = RetryPolicy(max_retries=3, initial_delay=0.1)

    # Transient error should retry until max_retries
    assert policy.should_retry(FailureType.TRANSIENT, attempt=0) is True
    assert policy.should_retry(FailureType.TRANSIENT, attempt=1) is True
    assert policy.should_retry(FailureType.TRANSIENT, attempt=2) is True
    assert policy.should_retry(FailureType.TRANSIENT, attempt=3) is False  # Reached limit

    # Authorization and Safety must NEVER blindly retry
    assert policy.should_retry(FailureType.AUTHORIZATION, attempt=0) is False
    assert policy.should_retry(FailureType.SAFETY, attempt=0) is False

    # Backoff delay increases with attempt
    d0 = policy.compute_delay(0)
    d1 = policy.compute_delay(1)
    d2 = policy.compute_delay(2)
    assert d0 < d1 < d2


def test_fallback_manager_compute_and_model():
    # GPU -> CPU fallback
    fb1 = FallbackManager.get_compute_fallback("gpu", privacy="local_only")
    assert fb1 == "cpu"

    # CPU -> Remote allowed only when remote_allowed
    fb2 = FallbackManager.get_compute_fallback("cpu", privacy="remote_allowed")
    assert fb2 == "remote"

    # CPU -> Remote blocked when local_only
    fb3 = FallbackManager.get_compute_fallback("cpu", privacy="local_only")
    assert fb3 is None

    # Model fallback
    mfb = FallbackManager.get_model_fallback("openai/gpt-oss-120b")
    assert mfb == "openai/gpt-oss-20b"


def test_replanner_dynamic_graph_repair():
    s1 = TaskStep(id="s1", name="Fetch API", agent_id="research_agent", action=Action(action_type="http.get"), dependencies=[], status=StepStatus.COMPLETED)
    s2 = TaskStep(id="s2", name="Browse Details", agent_id="browser_agent", action=Action(action_type="browser.navigate"), dependencies=["s1"], status=StepStatus.FAILED)
    s3 = TaskStep(id="s3", name="Summarize", agent_id="document_agent", action=Action(action_type="document.write"), dependencies=["s2"], status=StepStatus.PENDING)

    plan = TaskPlan(goal="Browse and summarize", steps=[s1, s2, s3])
    task = Task(goal="Browse and summarize", plan=plan)

    new_plan = Replanner.replan_failed_step(
        task=task,
        failed_step=s2,
        failure_reason="Browser crashed with timeout",
    )

    assert new_plan is not None
    # 4 steps: s1 (completed), s2 (skipped), replacement step (http.get fallback), s3 (updated dependency)
    assert len(new_plan.steps) == 4

    step_map = {s.id: s for s in new_plan.steps}
    # Original s2 marked skipped
    assert step_map["s2"].status == StepStatus.SKIPPED

    # Find replacement step
    replacements = [s for s in new_plan.steps if "(Fallback)" in s.name]
    assert len(replacements) == 1
    repl_step = replacements[0]
    assert repl_step.action.action_type == "http.get"

    # Downstream s3 now depends on repl_step.id instead of s2
    s3_new = step_map["s3"]
    assert repl_step.id in s3_new.dependencies
    assert "s2" not in s3_new.dependencies


def test_partial_success_evaluation():
    s1 = TaskStep(id="s1", name="Step 1", agent_id="research_agent", action=Action(action_type="op"), status=StepStatus.COMPLETED)
    s2 = TaskStep(id="s2", name="Step 2", agent_id="research_agent", action=Action(action_type="op"), status=StepStatus.FAILED)

    task = Task(goal="Partial test", plan=TaskPlan(goal="Partial test", steps=[s1, s2]))
    eval_res = Replanner.evaluate_partial_success(task)

    assert eval_res["status"] == "partial"
    assert eval_res["completed_count"] == 1
    assert eval_res["failed_count"] == 1
