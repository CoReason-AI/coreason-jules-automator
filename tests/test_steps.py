from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from coreason_jules_automator.async_api.scm import AsyncGeminiInterface, AsyncGitHubInterface
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
async def test_security_scan_step_failure(mock_settings: Settings) -> None:
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)
    mock_gemini.security_scan = AsyncMock(side_effect=RuntimeError("Scan Error"))

    step = SecurityScanStep(settings=mock_settings, gemini=mock_gemini)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is False
    assert "Scan Error" in result.message


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
async def test_code_review_step_success(mock_settings: Settings) -> None:
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)
    mock_gemini.code_review = AsyncMock()

    step = CodeReviewStep(settings=mock_settings, gemini=mock_gemini)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is True
    mock_gemini.code_review.assert_awaited_once()


@pytest.mark.asyncio
async def test_code_review_step_failure(mock_settings: Settings) -> None:
    mock_gemini = MagicMock(spec=AsyncGeminiInterface)
    mock_gemini.code_review = AsyncMock(side_effect=RuntimeError("Review Error"))

    step = CodeReviewStep(settings=mock_settings, gemini=mock_gemini)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is False
    assert "Review Error" in result.message


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
async def test_git_push_step_success(mock_settings: Settings) -> None:
    mock_janitor = MagicMock(spec=JanitorService)
    mock_git = MagicMock(spec=AsyncGitHubInterface)
    mock_git.push_to_branch = AsyncMock(return_value=True)

    step = GitPushStep(janitor=mock_janitor, git=mock_git)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is True
    mock_git.push_to_branch.assert_awaited()


@pytest.mark.asyncio
async def test_git_push_step_no_changes(mock_settings: Settings) -> None:
    mock_janitor = MagicMock(spec=JanitorService)
    mock_git = MagicMock(spec=AsyncGitHubInterface)
    mock_git.push_to_branch = AsyncMock(return_value=False)

    step = GitPushStep(janitor=mock_janitor, git=mock_git)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is True
    assert "No changes" in result.message


@pytest.mark.asyncio
async def test_git_push_step_failure(mock_settings: Settings) -> None:
    mock_janitor = MagicMock(spec=JanitorService)
    mock_git = MagicMock(spec=AsyncGitHubInterface)
    mock_git.push_to_branch = AsyncMock(side_effect=RuntimeError("Push Error"))

    step = GitPushStep(janitor=mock_janitor, git=mock_git)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    result = await step.execute(context)
    assert result.success is False
    assert "Push Error" in result.message


@pytest.mark.asyncio
async def test_ci_polling_step_success(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    mock_github.get_pr_checks = AsyncMock(
        return_value=[PullRequestStatus(name="check1", status="completed", conclusion="success", url="http://url")]
    )

    step = CIPollingStep(github=mock_github)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await step.execute(context)

    assert result.success is True
    assert context.pipeline_data["ci_passed"] is True
    assert len(context.pipeline_data["ci_checks"]) == 1


@pytest.mark.asyncio
async def test_ci_polling_step_failure_sets_context(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    mock_github.get_pr_checks = AsyncMock(
        return_value=[PullRequestStatus(name="check1", status="completed", conclusion="failure", url="http://url")]
    )

    step = CIPollingStep(github=mock_github)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await step.execute(context)

    # Step itself succeeds (polling finished)
    assert result.success is True
    # But context data shows failure
    assert context.pipeline_data["ci_passed"] is False


@pytest.mark.asyncio
async def test_ci_polling_step_timeout(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    # Always in progress
    mock_github.get_pr_checks = AsyncMock(
        return_value=[PullRequestStatus(name="check1", status="in_progress", conclusion=None, url="http://url")]
    )

    step = CIPollingStep(github=mock_github)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await step.execute(context)

    assert result.success is False
    assert "Timeout" in result.message


@pytest.mark.asyncio
async def test_ci_polling_step_error(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    # Raise error
    mock_github.get_pr_checks = AsyncMock(side_effect=RuntimeError("API Error"))

    step = CIPollingStep(github=mock_github)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await step.execute(context)

    assert result.success is False
    assert "Timeout" in result.message  # Retries until timeout


@pytest.mark.asyncio
async def test_ci_polling_step_fetch_error_retry_failure(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    # Raise error repeatedly to trigger retry failure log
    mock_github.get_pr_checks = AsyncMock(side_effect=RuntimeError("Fetch Fail"))

    step = CIPollingStep(github=mock_github)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with patch("coreason_jules_automator.strategies.steps.logger") as mock_logger:
            result = await step.execute(context)
            assert result.success is False
            # Verify the warning log in the retry loop was called
            assert any("Poll attempt failed" in str(c) for c in mock_logger.warning.call_args_list)


@pytest.mark.asyncio
async def test_log_analysis_step_janitor_error(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    # Return failure so analysis runs
    mock_github.get_latest_run_log.side_effect = lambda b: (x for x in ["log"])  # synchronous iterator? No, needs async

    async def mock_stream(branch_name: str) -> AsyncGenerator[str, None]:
        yield "log"

    mock_github.get_latest_run_log = mock_stream

    mock_janitor = MagicMock(spec=JanitorService)
    # Raise error during summarization
    mock_janitor.summarize_logs = AsyncMock(side_effect=Exception("Janitor Error"))

    step = LogAnalysisStep(github=mock_github, janitor=mock_janitor)

    context = OrchestrationContext(
        task_id="t1",
        branch_name="b1",
        session_id="s1",
        pipeline_data={
            "ci_passed": False,
            "ci_checks": [PullRequestStatus(name="check1", status="completed", conclusion="failure", url="http://url")],
        },
    )

    with pytest.raises(Exception, match="Janitor Error"):
        await step.execute(context)


@pytest.mark.asyncio
async def test_log_analysis_step_runs_on_failure(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    mock_github.get_latest_run_log = MagicMock()

    # Mock log stream
    async def mock_stream(branch_name: str) -> AsyncGenerator[str, None]:
        yield "Error log line"

    mock_github.get_latest_run_log.side_effect = mock_stream

    mock_janitor = MagicMock(spec=JanitorService)
    mock_janitor.summarize_logs = AsyncMock(return_value="Summary of error")

    step = LogAnalysisStep(github=mock_github, janitor=mock_janitor)

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
    mock_janitor.summarize_logs.assert_called()


@pytest.mark.asyncio
async def test_log_analysis_step_skips_on_success(mock_settings: Settings) -> None:
    step = LogAnalysisStep(github=MagicMock(), janitor=MagicMock())
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1", pipeline_data={"ci_passed": True})

    result = await step.execute(context)
    assert result.success is True
    assert "No analysis needed" in result.message


@pytest.mark.asyncio
async def test_log_analysis_step_large_logs(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)

    # Mock log stream
    async def mock_stream(branch_name: str) -> AsyncGenerator[str, None]:
        for i in range(2500):
            yield f"log line {i}"

    mock_github.get_latest_run_log.side_effect = mock_stream

    mock_janitor = MagicMock(spec=JanitorService)
    mock_janitor.summarize_logs = AsyncMock(return_value="Summary of error")

    step = LogAnalysisStep(github=mock_github, janitor=mock_janitor)

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
    mock_janitor.summarize_logs.assert_called()
    # Verify truncation happened in arguments passed to janitor
    args = mock_janitor.summarize_logs.call_args[0][0]
    assert "log line 2499" in args
    assert "log line 0" not in args


@pytest.mark.asyncio
async def test_log_analysis_step_stream_error(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)

    async def mock_stream(branch_name: str) -> AsyncGenerator[str, None]:
        raise Exception("Stream failed")
        yield "unreachable"

    mock_github.get_latest_run_log.side_effect = mock_stream

    mock_janitor = MagicMock(spec=JanitorService)
    mock_janitor.summarize_logs = AsyncMock(return_value="Summary of error")

    step = LogAnalysisStep(github=mock_github, janitor=mock_janitor)

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
