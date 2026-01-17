from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr
from tenacity import RetryError

from coreason_jules_automator.async_api.llm import AsyncLLMClient
from coreason_jules_automator.async_api.scm import AsyncGeminiInterface, AsyncGitHubInterface, AsyncGitInterface
from coreason_jules_automator.config import Settings
from coreason_jules_automator.domain.context import OrchestrationContext
from coreason_jules_automator.domain.scm import PullRequestStatus
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.strategies.steps import (
    CIPollingStep,
    CodeReviewStep,
    GitPushStep,
    LogAnalysisStep,
    SecurityScanStep,
)


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        repo_name="dummy/repo",
        GITHUB_TOKEN=SecretStr("dummy_token"),
        GOOGLE_API_KEY=SecretStr("dummy_key"),
        max_retries=5,
        extensions_enabled=["security", "code-review"],
        OPENAI_API_KEY=SecretStr("sk-dummy"),
        DEEPSEEK_API_KEY=SecretStr("sk-dummy"),
        SSH_PRIVATE_KEY=SecretStr("dummy_key"),
    )


# --- SecurityScanStep Tests ---


@pytest.mark.asyncio
async def test_security_scan_step(mock_settings: Settings) -> None:
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)
    mock_gemini.security_scan = AsyncMock()

    step = SecurityScanStep(settings=mock_settings, gemini=mock_gemini)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is True
    mock_gemini.security_scan.assert_awaited_once()


@pytest.mark.asyncio
async def test_security_scan_step_disabled(mock_settings: Settings) -> None:
    mock_settings.extensions_enabled = []
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)

    step = SecurityScanStep(settings=mock_settings, gemini=mock_gemini)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is True
    assert "disabled" in result.message
    mock_gemini.security_scan.assert_not_awaited()


@pytest.mark.asyncio
async def test_security_scan_step_failure(mock_settings: Settings) -> None:
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)
    mock_gemini.security_scan = AsyncMock(side_effect=RuntimeError("Scan failed"))

    step = SecurityScanStep(settings=mock_settings, gemini=mock_gemini)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is False
    assert "Security Scan failed: Scan failed" in result.message


# --- CodeReviewStep Tests ---


@pytest.mark.asyncio
async def test_code_review_step_success(mock_settings: Settings) -> None:
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)
    mock_gemini.code_review = AsyncMock()

    step = CodeReviewStep(settings=mock_settings, gemini=mock_gemini)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is True
    assert "passed" in result.message
    mock_gemini.code_review.assert_awaited_once()


@pytest.mark.asyncio
async def test_code_review_step_disabled(mock_settings: Settings) -> None:
    mock_settings.extensions_enabled = []
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)

    step = CodeReviewStep(settings=mock_settings, gemini=mock_gemini)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is True
    assert "disabled" in result.message
    mock_gemini.code_review.assert_not_awaited()


@pytest.mark.asyncio
async def test_code_review_step_failure(mock_settings: Settings) -> None:
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)
    mock_gemini.code_review = AsyncMock(side_effect=RuntimeError("Review failed"))

    step = CodeReviewStep(settings=mock_settings, gemini=mock_gemini)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is False
    assert "Code Review failed: Review failed" in result.message


# --- GitPushStep Tests ---


@pytest.mark.asyncio
async def test_git_push_step_success(mock_settings: Settings) -> None:
    mock_git = MagicMock(spec=AsyncGitInterface)
    mock_git.push_to_branch = AsyncMock(return_value=True)
    mock_janitor = MagicMock(spec=JanitorService)
    mock_janitor.sanitize_commit.return_value = "clean message"

    step = GitPushStep(janitor=mock_janitor, git=mock_git)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is True
    assert "pushed successfully" in result.message
    mock_git.push_to_branch.assert_awaited_with("b1", "clean message")


@pytest.mark.asyncio
async def test_git_push_step_no_changes(mock_settings: Settings) -> None:
    mock_git = MagicMock(spec=AsyncGitInterface)
    mock_git.push_to_branch = AsyncMock(return_value=False)
    mock_janitor = MagicMock(spec=JanitorService)
    mock_janitor.sanitize_commit.return_value = "clean message"

    step = GitPushStep(janitor=mock_janitor, git=mock_git)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is True
    assert "No changes detected" in result.message


@pytest.mark.asyncio
async def test_git_push_step_failure(mock_settings: Settings) -> None:
    mock_git = MagicMock(spec=AsyncGitInterface)
    mock_git.push_to_branch = AsyncMock(side_effect=RuntimeError("Git error"))
    mock_janitor = MagicMock(spec=JanitorService)
    mock_janitor.sanitize_commit.return_value = "clean message"

    step = GitPushStep(janitor=mock_janitor, git=mock_git)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is False
    assert "Failed to push code: Git error" in result.message


# --- CIPollingStep Tests ---


@pytest.mark.asyncio
async def test_ci_polling_step_success(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    mock_github.get_pr_checks = AsyncMock(
        return_value=[PullRequestStatus(name="check1", status="completed", conclusion="success", url="http://url")]
    )
    mock_emitter = MagicMock()
    step = CIPollingStep(github=mock_github, event_emitter=mock_emitter)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await step.execute(context)

    assert result.success is True
    assert context.pipeline_data["ci_passed"] is True
    assert len(context.pipeline_data["ci_checks"]) == 1
    # Verify emit was called to cover lines
    assert mock_emitter.emit.called


@pytest.mark.asyncio
async def test_ci_polling_step_failure_sets_context(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    mock_github.get_pr_checks = AsyncMock(
        return_value=[PullRequestStatus(name="check1", status="completed", conclusion="failure", url="http://url")]
    )
    mock_emitter = MagicMock()
    step = CIPollingStep(github=mock_github, event_emitter=mock_emitter)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await step.execute(context)

    # Step itself succeeds (polling finished)
    assert result.success is True
    # But context data shows failure
    assert context.pipeline_data["ci_passed"] is False
    assert mock_emitter.emit.called


@pytest.mark.asyncio
async def test_ci_polling_step_timeout(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)

    # Mocking RetryError to simulate timeout from tenacity
    class MockAsyncRetrying:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __aiter__(self) -> "MockAsyncRetrying":
            return self

        async def __anext__(self) -> None:
            raise RetryError(last_attempt=MagicMock())

    step = CIPollingStep(github=mock_github)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    with patch("coreason_jules_automator.strategies.steps.AsyncRetrying", MockAsyncRetrying):
        result = await step.execute(context)

    assert result.success is False
    assert "Timeout: Checks did not complete" in result.message


@pytest.mark.asyncio
async def test_ci_polling_step_loop_exit(mock_settings: Settings) -> None:
    # Test unexpected loop exit
    mock_github = MagicMock(spec=AsyncGitHubInterface)

    class MockAsyncRetrying:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __aiter__(self) -> "MockAsyncRetrying":
            return self

        async def __anext__(self) -> None:
            raise StopAsyncIteration

    step = CIPollingStep(github=mock_github)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    with patch("coreason_jules_automator.strategies.steps.AsyncRetrying", MockAsyncRetrying):
        result = await step.execute(context)

    assert result.success is False
    assert "Polling loop exited unexpectedly" in result.message


@pytest.mark.asyncio
async def test_ci_polling_step_fetch_error(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    mock_github.get_pr_checks = AsyncMock(
        side_effect=[
            RuntimeError("API error"),
            [PullRequestStatus(name="check1", status="completed", conclusion="success", url="url")],
        ]
    )

    step = CIPollingStep(github=mock_github)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    with patch("asyncio.sleep", new_callable=AsyncMock):  # fast forward
        result = await step.execute(context)

    assert result.success is True
    assert mock_github.get_pr_checks.call_count == 2


@pytest.mark.asyncio
async def test_ci_polling_step_not_completed(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    # First call returns in_progress, second returns completed
    mock_github.get_pr_checks = AsyncMock(
        side_effect=[
            [PullRequestStatus(name="check1", status="in_progress", conclusion=None, url="url")],
            [PullRequestStatus(name="check1", status="completed", conclusion="success", url="url")],
        ]
    )

    step = CIPollingStep(github=mock_github)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await step.execute(context)

    assert result.success is True
    assert mock_github.get_pr_checks.call_count == 2


# --- LogAnalysisStep Tests ---


@pytest.mark.asyncio
async def test_log_analysis_step_runs_on_failure(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    mock_github.get_latest_run_log = MagicMock()

    # Mock log stream
    async def mock_stream(branch_name: str) -> AsyncGenerator[str, None]:
        yield "Error log line"

    mock_github.get_latest_run_log.side_effect = mock_stream

    mock_janitor = MagicMock(spec=JanitorService)
    mock_janitor.build_summarize_request = MagicMock()

    mock_llm = MagicMock(spec=AsyncLLMClient)
    mock_llm.execute = AsyncMock(return_value=MagicMock(content="Summary of error"))

    mock_emitter = MagicMock()
    step = LogAnalysisStep(github=mock_github, janitor=mock_janitor, llm_client=mock_llm, event_emitter=mock_emitter)

    context = OrchestrationContext(
        task_id="t1",
        branch_name="b1",
        session_id="s1",
        pipeline_data={
            "ci_passed": False,
            "ci_checks": [PullRequestStatus(name="check1", status="completed", conclusion="failure", url="http://url")],
        },
    )

    result = await step.execute(context)

    assert result.success is False
    assert "Summary of error" in result.message
    mock_janitor.build_summarize_request.assert_called()
    assert mock_emitter.emit.called


@pytest.mark.asyncio
async def test_log_analysis_step_skips_on_success(mock_settings: Settings) -> None:
    step = LogAnalysisStep(github=MagicMock(), janitor=MagicMock(), llm_client=MagicMock())
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1", pipeline_data={"ci_passed": True})

    result = await step.execute(context)
    assert result.success is True
    assert "No analysis needed" in result.message


@pytest.mark.asyncio
async def test_log_analysis_step_no_llm_client(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    mock_github.get_latest_run_log = MagicMock()

    async def mock_stream(branch_name: str) -> AsyncGenerator[str, None]:
        yield "Error log line"

    mock_github.get_latest_run_log.side_effect = mock_stream

    step = LogAnalysisStep(github=mock_github, janitor=MagicMock(), llm_client=None)

    context = OrchestrationContext(
        task_id="t1",
        branch_name="b1",
        session_id="s1",
        pipeline_data={
            "ci_passed": False,
            "ci_checks": [PullRequestStatus(name="check1", status="completed", conclusion="failure", url="http://url")],
        },
    )

    result = await step.execute(context)
    assert result.success is False
    assert "CI checks failed" in result.message
    assert "Error log line" in result.message


@pytest.mark.asyncio
async def test_log_analysis_step_stream_error(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    mock_github.get_latest_run_log = MagicMock()

    async def mock_stream(branch_name: str) -> AsyncGenerator[str, None]:
        raise Exception("Stream failed")
        yield "unreachable"  # Make it a generator

    mock_github.get_latest_run_log.side_effect = mock_stream

    # Even if stream fails, if we have LLM, it tries to summarize the error message
    mock_llm = MagicMock(spec=AsyncLLMClient)
    mock_llm.execute = AsyncMock(return_value=MagicMock(content="Summary of error"))

    step = LogAnalysisStep(github=mock_github, janitor=MagicMock(), llm_client=mock_llm)

    # Cast to Any to satisfy MyPy that doesn't know this is a Mock with 'called' attribute
    # or rely on .assert_called() which is safer if available, but 'called' is simple property
    step.janitor = MagicMock()

    context = OrchestrationContext(
        task_id="t1",
        branch_name="b1",
        session_id="s1",
        pipeline_data={
            "ci_passed": False,
            "ci_checks": [PullRequestStatus(name="check1", status="completed", conclusion="failure", url="http://url")],
        },
    )

    result = await step.execute(context)
    assert result.success is False
    # It should have caught the exception and appended it to logs
    # We can check if janitor was called with the exception message
    assert step.janitor.build_summarize_request.called


@pytest.mark.asyncio
async def test_log_analysis_step_llm_failure(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    mock_github.get_latest_run_log = MagicMock()

    async def mock_stream(branch_name: str) -> AsyncGenerator[str, None]:
        yield "log"

    mock_github.get_latest_run_log.side_effect = mock_stream

    mock_llm = MagicMock(spec=AsyncLLMClient)
    mock_llm.execute = AsyncMock(side_effect=Exception("LLM boom"))

    step = LogAnalysisStep(github=mock_github, janitor=JanitorService(prompt_manager=MagicMock()), llm_client=mock_llm)
    # This assignment triggers method-assign error in mypy because we are replacing a method with a Mock
    # We can use unittest.mock.patch.object or just ignore type
    step.janitor.build_summarize_request = MagicMock()  # type: ignore

    context = OrchestrationContext(
        task_id="t1",
        branch_name="b1",
        session_id="s1",
        pipeline_data={
            "ci_passed": False,
            "ci_checks": [PullRequestStatus(name="check1", status="completed", conclusion="failure", url="http://url")],
        },
    )

    result = await step.execute(context)
    assert result.success is False
    assert "Log summarization failed" in result.message


@pytest.mark.asyncio
async def test_log_analysis_step_no_checks_failed(mock_settings: Settings) -> None:
    # Case where ci_passed is False but checks list doesn't have a failure (inconsistent state or checks empty)
    step = LogAnalysisStep(github=MagicMock(), janitor=MagicMock(), llm_client=MagicMock())
    context = OrchestrationContext(
        task_id="t1",
        branch_name="b1",
        session_id="s1",
        pipeline_data={
            "ci_passed": False,
            "ci_checks": [],
        },
    )

    result = await step.execute(context)
    assert result.success is False
    assert "could not identify specific check failure" in result.message


@pytest.mark.asyncio
async def test_ci_polling_step_empty_checks(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    # First call returns empty list, second call returns completed list
    mock_github.get_pr_checks = AsyncMock(
        side_effect=[
            [],
            [PullRequestStatus(name="check1", status="completed", conclusion="success", url="url")],
        ]
    )

    step = CIPollingStep(github=mock_github)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await step.execute(context)

    assert result.success is True
    assert mock_github.get_pr_checks.call_count == 2


@pytest.mark.asyncio
async def test_log_analysis_step_large_logs(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    mock_github.get_latest_run_log = MagicMock()

    async def mock_stream(branch_name: str) -> AsyncGenerator[str, None]:
        for i in range(2005):
            yield f"log line {i}"

    mock_github.get_latest_run_log.side_effect = mock_stream

    mock_llm = MagicMock(spec=AsyncLLMClient)
    mock_llm.execute = AsyncMock(return_value=MagicMock(content="Summary"))

    step = LogAnalysisStep(github=mock_github, janitor=MagicMock(), llm_client=mock_llm)
    step.janitor = MagicMock()

    context = OrchestrationContext(
        task_id="t1",
        branch_name="b1",
        session_id="s1",
        pipeline_data={
            "ci_passed": False,
            "ci_checks": [PullRequestStatus(name="check1", status="completed", conclusion="failure", url="http://url")],
        },
    )

    result = await step.execute(context)

    assert result.success is False
    # Check if janitor was called with truncated logs
    # We can inspect the argument passed to build_summarize_request
    call_args = step.janitor.build_summarize_request.call_args
    assert call_args is not None
    log_snippet = call_args[0][0]

    # We expect the last lines to be present, and total lines to be around 2000
    # The implementation keeps the tail.
    assert "log line 2004" in log_snippet
    assert "log line 0" not in log_snippet  # because it should have been popped
