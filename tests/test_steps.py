from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from coreason_jules_automator.async_api.llm import AsyncLLMClient
from coreason_jules_automator.async_api.scm import AsyncGeminiInterface, AsyncGitHubInterface
from coreason_jules_automator.config import Settings
from coreason_jules_automator.domain.context import OrchestrationContext
from coreason_jules_automator.domain.scm import PullRequestStatus
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.strategies.steps import (
    CIPollingStep,
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
    mock_llm.execute = AsyncMock(return_value=MagicMock(summary="Summary of error"))

    step = LogAnalysisStep(github=mock_github, janitor=mock_janitor, llm_client=mock_llm)

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


@pytest.mark.asyncio
async def test_log_analysis_step_skips_on_success(mock_settings: Settings) -> None:
    step = LogAnalysisStep(github=MagicMock(), janitor=MagicMock(), llm_client=MagicMock())
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
    mock_janitor.build_summarize_request = MagicMock()

    mock_llm = MagicMock(spec=AsyncLLMClient)
    # Fix: Return object with summary attribute
    mock_llm.execute = AsyncMock(return_value=MagicMock(summary="Summary of error"))

    step = LogAnalysisStep(github=mock_github, janitor=mock_janitor, llm_client=mock_llm)

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
    mock_janitor.build_summarize_request.assert_called()
    # Verify truncation happened in arguments passed to janitor
    args = mock_janitor.build_summarize_request.call_args[0][0]
    assert "log line 2499" in args
    assert "log line 0" not in args


@pytest.mark.asyncio
async def test_log_analysis_step_stream_error(mock_settings: Settings) -> None:
    mock_github = MagicMock(spec=AsyncGitHubInterface)

    async def mock_stream(branch_name: str) -> AsyncGenerator[str, None]:
        raise Exception("Stream failed")
        yield "unreachable"

    mock_github.get_latest_run_log.side_effect = mock_stream

    mock_llm = MagicMock(spec=AsyncLLMClient)
    # Fix: Return object with summary attribute
    mock_llm.execute = AsyncMock(return_value=MagicMock(summary="Summary of error"))

    step = LogAnalysisStep(github=mock_github, janitor=MagicMock(), llm_client=mock_llm)
    step.janitor = MagicMock()  # Ensure janitor is a mock

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
