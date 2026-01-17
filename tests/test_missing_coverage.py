from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from typer.testing import CliRunner
from coreason_jules_automator.cli import app
from coreason_jules_automator.strategies.steps import CIPollingStep, LogAnalysisStep
from coreason_jules_automator.ui.console import RichConsoleEmitter
from coreason_jules_automator.async_api.scm import AsyncGitHubInterface
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.domain.context import OrchestrationContext
from coreason_jules_automator.domain.scm import PullRequestStatus
from coreason_jules_automator.strategies.steps import TryAgain

runner = CliRunner()

def test_campaign_exception() -> None:
    """Test campaign run with unexpected exception."""
    with patch("coreason_jules_automator.cli.Container"), \
         patch("coreason_jules_automator.cli.RichConsoleEmitter"), \
         patch("coreason_jules_automator.cli.logger") as mock_logger, \
         patch("coreason_jules_automator.cli.asyncio.run", side_effect=Exception("Crash inside campaign")):

        result = runner.invoke(app, ["campaign", "Task", "--base", "dev", "--count", "1"])

        assert result.exit_code == 1
        mock_logger.exception.assert_called()
        assert "Crash inside campaign" in str(mock_logger.exception.call_args)

@pytest.mark.asyncio
async def test_ci_polling_step_fetch_error() -> None:
    """Test CIPollingStep handling fetch error (Line 221)."""
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    # 1. RuntimeError -> Hits Line 184 (except RuntimeError).
    # 2. [] -> Hits Line 191 (Checks not completed).
    # 3. [Status(completed, success)] -> Success.
    mock_github.get_pr_checks = AsyncMock(side_effect=[
        RuntimeError("Fetch failed"),
        [],
        [PullRequestStatus(name="c1", status="completed", conclusion="success", url="u1")]
    ])

    step = CIPollingStep(github=mock_github)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    with patch("coreason_jules_automator.strategies.steps.logger") as mock_logger, \
         patch("asyncio.sleep", new_callable=AsyncMock):

        result = await step.execute(context)

    assert result.success is True
    # Verify warning was logged
    assert any("Poll attempt failed" in str(c) for c in mock_logger.warning.call_args_list)

@pytest.mark.asyncio
async def test_ci_polling_step_checks_not_completed() -> None:
    """Test CIPollingStep raises TryAgain when checks are not completed (Line 226)."""
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    # Return checks that are not completed.
    mock_github.get_pr_checks = AsyncMock(return_value=[
        PullRequestStatus(name="c1", status="in_progress", conclusion=None, url="u1")
    ])

    step = CIPollingStep(github=mock_github)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    with patch("asyncio.sleep", new_callable=AsyncMock):
         # Patch stop_after_attempt to 2 to be faster
         with patch("coreason_jules_automator.strategies.steps.stop_after_attempt") as mock_stop:
             # Stop after 2 attempts
             mock_stop.return_value = lambda rs: rs.attempt_number >= 2

             result = await step.execute(context)

    assert result.success is False
    assert "Timeout" in result.message

@pytest.mark.asyncio
async def test_log_analysis_step_janitor_exception() -> None:
    """Test LogAnalysisStep handling janitor exception (Line 310)."""
    mock_github = MagicMock(spec=AsyncGitHubInterface)

    mock_github.get_latest_run_log = MagicMock()
    async def mock_stream(branch_name: str):
        yield "some logs"
    mock_github.get_latest_run_log.side_effect = mock_stream

    mock_janitor = MagicMock(spec=JanitorService)
    mock_janitor.build_summarize_request.side_effect = Exception("Janitor Error")

    step = LogAnalysisStep(
        github=mock_github,
        janitor=mock_janitor,
        llm_client=MagicMock()
    )

    context = OrchestrationContext(
        task_id="t1",
        branch_name="b1",
        session_id="s1",
        pipeline_data={
            "ci_passed": False,
            "ci_checks": [PullRequestStatus(name="c1", status="completed", conclusion="failure", url="u1")]
        }
    )

    with patch("coreason_jules_automator.strategies.steps.logger") as mock_logger:
        result = await step.execute(context)

        assert result.success is False
        assert "Log summarization failed" in result.message
        # Verify exception logged (Line 314 handling)
        mock_logger.error.assert_called()
        assert "Janitor summarization failed" in str(mock_logger.error.call_args)

@pytest.mark.asyncio
async def test_ci_polling_step_loop_exit_unexpectedly() -> None:
    """Test CIPollingStep loop exits unexpectedly (Line 221)."""
    mock_github = MagicMock(spec=AsyncGitHubInterface)
    step = CIPollingStep(github=mock_github)
    context = OrchestrationContext(task_id="t1", branch_name="b1", session_id="s1")

    # Mock AsyncRetrying to NOT raise RetryError but finish iteration.
    with patch("coreason_jules_automator.strategies.steps.AsyncRetrying") as MockRetrying:
        mock_instance = MockRetrying.return_value
        mock_instance.__aiter__.return_value = mock_instance
        mock_instance.__anext__.side_effect = StopAsyncIteration

        result = await step.execute(context)

    assert result.success is False
    assert "Polling loop exited unexpectedly" in result.message

@pytest.mark.asyncio
async def test_log_analysis_step_no_failed_check_found() -> None:
    """Test LogAnalysisStep when no specific failed check is found (Line 314)."""
    step = LogAnalysisStep(
        github=MagicMock(),
        janitor=MagicMock(),
        llm_client=MagicMock()
    )

    context = OrchestrationContext(
        task_id="t1",
        branch_name="b1",
        session_id="s1",
        pipeline_data={
            "ci_passed": False,
            "ci_checks": [
                PullRequestStatus(name="c1", status="completed", conclusion="success", url="u1")
            ]
        }
    )

    result = await step.execute(context)

    assert result.success is False
    assert "CI checks failed but could not identify specific check failure" in result.message

def test_rich_console_emitter_stop_coverage() -> None:
    """Test RichConsoleEmitter.stop calls live.stop if live exists (Line 58-59)."""
    emitter = RichConsoleEmitter()
    mock_live = MagicMock()
    emitter.live = mock_live

    emitter.stop()

    mock_live.stop.assert_called_once()

def test_rich_console_emitter_warn_status() -> None:
    """Test RichConsoleEmitter handles 'warn' status correctly (Line 58-59)."""
    emitter = RichConsoleEmitter()
    emitter.checks["test_warn"] = {"status": "warn", "message": "Warning!"}

    table = emitter.generate_table()
    # verify execution
    assert len(table.rows) == 1
