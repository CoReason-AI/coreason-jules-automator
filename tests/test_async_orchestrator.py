from unittest.mock import AsyncMock, MagicMock, patch, ANY

import pytest

from coreason_jules_automator.async_api.agent import AsyncJulesAgent
from coreason_jules_automator.async_api.orchestrator import AsyncOrchestrator
from coreason_jules_automator.async_api.strategies import AsyncDefenseStrategy
from coreason_jules_automator.async_api.scm import AsyncGitInterface
from coreason_jules_automator.async_api.llm import AsyncLLMClient
from coreason_jules_automator.llm.janitor import JanitorService
from coreason_jules_automator.strategies.base import DefenseResult


@pytest.fixture(autouse=True)
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COREASON_REPO_NAME", "dummy/repo")
    monkeypatch.setenv("COREASON_GITHUB_TOKEN", "dummy_token")
    monkeypatch.setenv("COREASON_GOOGLE_API_KEY", "dummy_key")


@pytest.mark.asyncio
async def test_async_orchestrator_run_cycle_success() -> None:
    # Mocks
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.launch_session = AsyncMock(return_value="sid-123")
    mock_agent.wait_for_completion = AsyncMock(return_value=True)
    mock_agent.teleport_and_sync = AsyncMock(return_value=True)

    mock_strategy = MagicMock(spec=AsyncDefenseStrategy)
    mock_strategy.execute = AsyncMock(return_value=DefenseResult(success=True, message="All good"))

    orchestrator = AsyncOrchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
    )

    # Execute
    success, feedback = await orchestrator.run_cycle("Fix bug", "feature/bugfix")

    # Assertions
    assert success is True
    assert feedback == "Success"

    mock_agent.launch_session.assert_awaited_once()
    mock_agent.wait_for_completion.assert_awaited_once_with("sid-123")
    mock_agent.teleport_and_sync.assert_awaited_once()
    mock_strategy.execute.assert_awaited_once()

    # Check context passed to strategy
    call_args = mock_strategy.execute.call_args
    assert call_args is not None
    kwargs = call_args.kwargs
    context = kwargs.get("context")
    assert context is not None
    assert context["sid"] == "sid-123"
    assert context["branch_name"] == "feature/bugfix"


@pytest.mark.asyncio
async def test_async_orchestrator_run_cycle_retry() -> None:
    # Mocks
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.launch_session = AsyncMock(side_effect=["sid-1", "sid-2"])
    mock_agent.wait_for_completion = AsyncMock(return_value=True)
    mock_agent.teleport_and_sync = AsyncMock(return_value=True)

    mock_strategy = MagicMock(spec=AsyncDefenseStrategy)
    # Fail first time, succeed second time
    mock_strategy.execute = AsyncMock(
        side_effect=[
            DefenseResult(success=False, message="Lint error"),
            DefenseResult(success=True, message="All good"),
        ]
    )

    orchestrator = AsyncOrchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
    )

    # Execute
    success, feedback = await orchestrator.run_cycle("Fix bug", "feature/bugfix")

    # Assertions
    assert success is True
    assert feedback == "Success"

    assert mock_agent.launch_session.call_count == 2
    assert mock_agent.wait_for_completion.call_count == 2
    assert mock_strategy.execute.call_count == 2

    # Verify feedback injection in second call
    call_args_list = mock_agent.launch_session.call_args_list
    first_call_arg = call_args_list[0][0][0]
    second_call_arg = call_args_list[1][0][0]

    assert first_call_arg == "Fix bug"
    assert "Lint error" in second_call_arg
    assert "IMPORTANT" in second_call_arg


@pytest.mark.asyncio
async def test_async_orchestrator_run_cycle_agent_failure() -> None:
    # Mocks
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.launch_session = AsyncMock(return_value=None)  # Fail to launch

    mock_strategy = MagicMock(spec=AsyncDefenseStrategy)

    orchestrator = AsyncOrchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
    )

    # Execute
    success, feedback = await orchestrator.run_cycle("Fix bug", "feature/bugfix")

    # Assertions
    assert success is False
    assert "Failed to obtain Session ID" in feedback
    mock_strategy.execute.assert_not_awaited()

@pytest.mark.asyncio
async def test_async_orchestrator_run_cycle_wait_failure() -> None:
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.launch_session = AsyncMock(return_value="sid")
    mock_agent.wait_for_completion = AsyncMock(return_value=False)

    orchestrator = AsyncOrchestrator(agent=mock_agent, strategies=[])

    success, feedback = await orchestrator.run_cycle("Task", "branch")
    assert success is False
    assert "did not complete" in feedback

@pytest.mark.asyncio
async def test_async_orchestrator_run_cycle_teleport_failure() -> None:
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.launch_session = AsyncMock(return_value="sid")
    mock_agent.wait_for_completion = AsyncMock(return_value=True)
    mock_agent.teleport_and_sync = AsyncMock(return_value=False)

    orchestrator = AsyncOrchestrator(agent=mock_agent, strategies=[])

    success, feedback = await orchestrator.run_cycle("Task", "branch")
    assert success is False
    assert "Failed to sync" in feedback

@pytest.mark.asyncio
async def test_async_orchestrator_run_cycle_exception() -> None:
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.launch_session = AsyncMock(side_effect=Exception("Boom"))

    orchestrator = AsyncOrchestrator(agent=mock_agent, strategies=[])

    success, feedback = await orchestrator.run_cycle("Task", "branch")
    assert success is False
    assert "Boom" in feedback

@pytest.mark.asyncio
async def test_async_orchestrator_run_cycle_max_retries() -> None:
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.launch_session = AsyncMock(return_value="sid")
    mock_agent.wait_for_completion = AsyncMock(return_value=True)
    mock_agent.teleport_and_sync = AsyncMock(return_value=True)

    mock_strategy = MagicMock(spec=AsyncDefenseStrategy)
    mock_strategy.execute = AsyncMock(return_value=DefenseResult(success=False, message="Fail"))

    orchestrator = AsyncOrchestrator(agent=mock_agent, strategies=[mock_strategy])

    # Mock settings to have low retries
    with patch("coreason_jules_automator.async_api.orchestrator.get_settings") as mock_settings:
        mock_settings.return_value.max_retries = 2
        success, feedback = await orchestrator.run_cycle("Task", "branch")

    assert success is False
    assert feedback == "Fail"
    assert mock_strategy.execute.call_count == 2


@pytest.mark.asyncio
async def test_async_orchestrator_run_campaign_success() -> None:
    # Mocks
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.mission_complete = True # Simulate completion after first iteration
    mock_agent.launch_session = AsyncMock(return_value="sid-123")
    mock_agent.wait_for_completion = AsyncMock(return_value=True)
    mock_agent.teleport_and_sync = AsyncMock(return_value=True)

    mock_strategy = MagicMock(spec=AsyncDefenseStrategy)
    mock_strategy.execute = AsyncMock(return_value=DefenseResult(success=True))

    mock_git = MagicMock(spec=AsyncGitInterface)
    mock_git.checkout_new_branch = AsyncMock()
    mock_git.get_commit_log = AsyncMock(return_value="feat: cool feature")
    mock_git.merge_squash = AsyncMock()
    mock_git.delete_branch = AsyncMock()

    mock_janitor = MagicMock(spec=JanitorService)
    mock_janitor.sanitize_commit = MagicMock(return_value="feat: cool feature")
    mock_janitor.build_professionalize_request = MagicMock(return_value=MagicMock(messages=[], max_tokens=100))
    mock_janitor.parse_professionalize_response = MagicMock(return_value="feat: pro commit")

    mock_llm = MagicMock(spec=AsyncLLMClient)
    mock_llm.execute = AsyncMock(return_value=MagicMock(content="feat: pro commit"))

    orchestrator = AsyncOrchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        git_interface=mock_git,
        janitor_service=mock_janitor,
        llm_client=mock_llm
    )

    # Execute
    # Iterations=1 to limit loop if logic fails
    await orchestrator.run_campaign("Task", "develop", iterations=1)

    # Verify flow
    assert mock_git.checkout_new_branch.call_count >= 2 # 1 agg + 1 iter
    mock_git.merge_squash.assert_awaited()
    mock_git.delete_branch.assert_awaited()


@pytest.mark.asyncio
async def test_async_orchestrator_run_campaign_exception() -> None:
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_git = MagicMock(spec=AsyncGitInterface)
    # First call succeeds (setup), second call fails (iteration checkout)
    mock_git.checkout_new_branch = AsyncMock(side_effect=[None, Exception("Git Error")])
    # Cleanup should be called, and if it fails, it should be ignored
    mock_git.delete_branch = AsyncMock(side_effect=Exception("Cleanup Fail"))

    mock_janitor = MagicMock(spec=JanitorService)

    orchestrator = AsyncOrchestrator(
        agent=mock_agent,
        strategies=[],
        git_interface=mock_git,
        janitor_service=mock_janitor
    )

    await orchestrator.run_campaign("Task", "develop", iterations=1)

    # Should catch exception and attempt cleanup
    mock_git.delete_branch.assert_awaited()

@pytest.mark.asyncio
async def test_async_orchestrator_run_campaign_prof_failure() -> None:
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.mission_complete = True
    mock_agent.launch_session = AsyncMock(return_value="sid")
    mock_agent.wait_for_completion = AsyncMock(return_value=True)
    mock_agent.teleport_and_sync = AsyncMock(return_value=True)

    mock_strategy = MagicMock(spec=AsyncDefenseStrategy)
    mock_strategy.execute = AsyncMock(return_value=DefenseResult(success=True))

    mock_git = MagicMock(spec=AsyncGitInterface)
    mock_git.checkout_new_branch = AsyncMock()
    mock_git.get_commit_log = AsyncMock(return_value="raw log")
    mock_git.merge_squash = AsyncMock()
    mock_git.delete_branch = AsyncMock()

    mock_janitor = MagicMock(spec=JanitorService)
    # Raise error during request build
    mock_janitor.build_professionalize_request = MagicMock(side_effect=Exception("Prof Fail"))

    mock_llm = MagicMock(spec=AsyncLLMClient)

    orchestrator = AsyncOrchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        git_interface=mock_git,
        janitor_service=mock_janitor,
        llm_client=mock_llm
    )

    await orchestrator.run_campaign("Task", "develop", iterations=1)

    # Should fallback to sanitize_commit? No, fallback logic is:
    # if janitor and llm: try prof. if fail -> log error.
    # else: if janitor: sanitize.
    # Wait, the fallback is:
    # clean_msg = raw_log (default)
    # if janitor and llm: try prof.
    # else: if janitor: sanitize.
    # If prof fails, it just logs error. clean_msg remains raw_log.

    mock_git.merge_squash.assert_awaited_with(
        ANY, ANY, "raw log"
    )

@pytest.mark.asyncio
async def test_async_orchestrator_run_campaign_prof_retry_fail() -> None:
    # Test retry loop inside professionalize commit
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.mission_complete = True
    mock_agent.launch_session = AsyncMock(return_value="sid")
    mock_agent.wait_for_completion = AsyncMock(return_value=True)
    mock_agent.teleport_and_sync = AsyncMock(return_value=True)

    mock_strategy = MagicMock(spec=AsyncDefenseStrategy)
    mock_strategy.execute = AsyncMock(return_value=DefenseResult(success=True))

    mock_git = MagicMock(spec=AsyncGitInterface)
    mock_git.checkout_new_branch = AsyncMock()
    mock_git.get_commit_log = AsyncMock(return_value="raw log")
    mock_git.merge_squash = AsyncMock()
    mock_git.delete_branch = AsyncMock()

    mock_janitor = MagicMock(spec=JanitorService)
    mock_janitor.build_professionalize_request = MagicMock(return_value=MagicMock())

    mock_llm = MagicMock(spec=AsyncLLMClient)
    # Fail repeatedly
    mock_llm.execute = AsyncMock(side_effect=Exception("LLM Timeout"))

    orchestrator = AsyncOrchestrator(
        agent=mock_agent,
        strategies=[mock_strategy],
        git_interface=mock_git,
        janitor_service=mock_janitor,
        llm_client=mock_llm
    )

    await orchestrator.run_campaign("Task", "develop", iterations=1)

    # Assert retry logic: 3 attempts
    assert mock_llm.execute.call_count == 3
    # Merges with raw log
    mock_git.merge_squash.assert_awaited_with(ANY, ANY, "raw log")

@pytest.mark.asyncio
async def test_async_orchestrator_run_cycle_teleport_exception() -> None:
    # This specifically tests line 169
    mock_agent = MagicMock(spec=AsyncJulesAgent)
    mock_agent.launch_session = AsyncMock(return_value="sid")
    mock_agent.wait_for_completion = AsyncMock(return_value=True)
    # Raise exception instead of returning False
    mock_agent.teleport_and_sync = AsyncMock(side_effect=Exception("Teleport Boom"))

    orchestrator = AsyncOrchestrator(agent=mock_agent, strategies=[])

    success, feedback = await orchestrator.run_cycle("Task", "branch")
    assert success is False
    assert "Teleport Boom" in feedback
