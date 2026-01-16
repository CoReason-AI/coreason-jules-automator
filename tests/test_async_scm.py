from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from coreason_jules_automator.async_api.scm import AsyncGeminiInterface, AsyncGitHubInterface, AsyncGitInterface
from coreason_jules_automator.async_api.shell import AsyncShellExecutor
from coreason_jules_automator.exceptions import AuthError, NetworkError, ScmError
from coreason_jules_automator.utils.shell import CommandResult, ShellError

# --- AsyncGitInterface Tests ---


@pytest.mark.asyncio
async def test_git_has_changes_true() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(return_value=CommandResult(0, "M file.txt", ""))
    git = AsyncGitInterface(shell_executor=mock_shell)
    assert await git.has_changes() is True
    mock_shell.run.assert_awaited_with(["git", "status", "--porcelain"], check=True)


@pytest.mark.asyncio
async def test_git_has_changes_false() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(return_value=CommandResult(0, "", ""))
    git = AsyncGitInterface(shell_executor=mock_shell)
    assert await git.has_changes() is False


@pytest.mark.asyncio
async def test_git_has_changes_error() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(side_effect=ShellError("Fail", CommandResult(1, "", "Error")))
    git = AsyncGitInterface(shell_executor=mock_shell)
    assert await git.has_changes() is False


@pytest.mark.asyncio
async def test_git_push_to_branch_success() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    # 1. rm lock (ok)
    # 2. add (ok)
    # 3. status (has changes)
    # 4. commit (ok)
    # 5. push (ok)
    mock_shell.run = AsyncMock(
        side_effect=[
            CommandResult(0, "", ""),  # rm
            CommandResult(0, "", ""),  # add
            CommandResult(0, "M file", ""),  # status (called by has_changes)
            CommandResult(0, "", ""),  # commit
            CommandResult(0, "", ""),  # push
        ]
    )
    git = AsyncGitInterface(shell_executor=mock_shell)
    assert await git.push_to_branch("feat-1", "msg") is True
    assert mock_shell.run.call_count == 5


@pytest.mark.asyncio
async def test_git_push_to_branch_no_changes() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(
        side_effect=[
            CommandResult(0, "", ""),  # rm
            CommandResult(0, "", ""),  # add
            CommandResult(0, "", ""),  # status (empty)
        ]
    )
    git = AsyncGitInterface(shell_executor=mock_shell)
    assert await git.push_to_branch("feat-1", "msg") is False
    assert mock_shell.run.call_count == 3  # commit/push skipped


@pytest.mark.asyncio
async def test_git_push_to_branch_failure() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(side_effect=ShellError("Fail", CommandResult(1, "", "")))
    git = AsyncGitInterface(shell_executor=mock_shell)
    with pytest.raises(ScmError, match="Git push failed"):
        await git.push_to_branch("feat-1", "msg")


@pytest.mark.asyncio
async def test_git_push_network_error() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(side_effect=ShellError("Fail", CommandResult(1, "", "Connection timed out")))
    git = AsyncGitInterface(shell_executor=mock_shell)
    with pytest.raises(NetworkError, match="Git push failed"):
        await git.push_to_branch("feat-1", "msg")


@pytest.mark.asyncio
async def test_git_push_auth_error() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(side_effect=ShellError("Fail", CommandResult(1, "", "Permission denied (publickey)")))
    git = AsyncGitInterface(shell_executor=mock_shell)
    with pytest.raises(AuthError, match="Git push failed"):
        await git.push_to_branch("feat-1", "msg")


@pytest.mark.asyncio
async def test_git_checkout_new_branch() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(return_value=CommandResult(0, "", ""))
    git = AsyncGitInterface(shell_executor=mock_shell)

    await git.checkout_new_branch("new", "base", pull_base=True)
    assert mock_shell.run.call_count == 3
    # Verify calls
    mock_shell.run.assert_has_awaits(
        [
            call(["git", "checkout", "base"], check=True),
            call(["git", "pull", "origin", "base"], check=True),
            call(["git", "checkout", "-b", "new"], check=True),
        ]
    )


@pytest.mark.asyncio
async def test_git_checkout_new_branch_no_pull() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(return_value=CommandResult(0, "", ""))
    git = AsyncGitInterface(shell_executor=mock_shell)

    await git.checkout_new_branch("new", "base", pull_base=False)
    assert mock_shell.run.call_count == 2
    # Verify pull skipped


@pytest.mark.asyncio
async def test_git_checkout_new_branch_failure() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(side_effect=ShellError("Fail", CommandResult(1, "", "")))
    git = AsyncGitInterface(shell_executor=mock_shell)
    with pytest.raises(ScmError, match="Failed to checkout new branch"):
        await git.checkout_new_branch("new", "base")


@pytest.mark.asyncio
async def test_git_merge_squash() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(return_value=CommandResult(0, "", ""))
    git = AsyncGitInterface(shell_executor=mock_shell)

    await git.merge_squash("src", "tgt", "msg")
    assert mock_shell.run.call_count == 4  # checkout, merge, commit, push


@pytest.mark.asyncio
async def test_git_merge_squash_failure() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(side_effect=ShellError("Fail", CommandResult(1, "", "")))
    git = AsyncGitInterface(shell_executor=mock_shell)
    with pytest.raises(ScmError, match="Failed to squash merge"):
        await git.merge_squash("src", "tgt", "msg")


@pytest.mark.asyncio
async def test_git_get_commit_log() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(return_value=CommandResult(0, "Log content", ""))
    git = AsyncGitInterface(shell_executor=mock_shell)

    log = await git.get_commit_log("base", "head")
    assert log == "Log content"


@pytest.mark.asyncio
async def test_git_get_commit_log_failure() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(side_effect=ShellError("Fail", CommandResult(1, "", "")))
    git = AsyncGitInterface(shell_executor=mock_shell)
    with pytest.raises(ScmError, match="Failed to get commit log"):
        await git.get_commit_log("base", "head")


@pytest.mark.asyncio
async def test_git_delete_branch() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(return_value=CommandResult(0, "", ""))
    git = AsyncGitInterface(shell_executor=mock_shell)

    await git.delete_branch("feat")
    assert mock_shell.run.call_count == 2  # remote delete, local delete


@pytest.mark.asyncio
async def test_git_delete_branch_failure_logged() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    # Fail remote, succeed local
    mock_shell.run = AsyncMock(
        side_effect=[ShellError("Fail Remote", CommandResult(1, "", "")), CommandResult(0, "", "")]
    )
    git = AsyncGitInterface(shell_executor=mock_shell)

    # Should not raise
    await git.delete_branch("feat")
    assert mock_shell.run.call_count == 2

    # Fail local too
    mock_shell.run = AsyncMock(side_effect=ShellError("Fail", CommandResult(1, "", "")))
    await git.delete_branch("feat")


# --- AsyncGitHubInterface Tests ---


@pytest.mark.asyncio
async def test_github_init_no_executable() -> None:
    with patch("shutil.which", return_value=None):
        with patch("coreason_jules_automator.async_api.scm.logger") as mock_logger:
            AsyncGitHubInterface()
            mock_logger.warning.assert_called()


@pytest.mark.asyncio
async def test_github_get_pr_checks() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(return_value=CommandResult(0, '[{"name": "check1"}]', ""))
    gh = AsyncGitHubInterface(shell_executor=mock_shell)

    checks = await gh.get_pr_checks()
    assert len(checks) == 1
    assert checks[0]["name"] == "check1"


@pytest.mark.asyncio
async def test_github_get_pr_checks_not_list() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(return_value=CommandResult(0, '{"name": "check1"}', ""))
    gh = AsyncGitHubInterface(shell_executor=mock_shell)

    with pytest.raises(ScmError, match="expected list"):
        await gh.get_pr_checks()


@pytest.mark.asyncio
async def test_github_get_pr_checks_json_error() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(return_value=CommandResult(0, "invalid json", ""))
    gh = AsyncGitHubInterface(shell_executor=mock_shell)

    with pytest.raises(ScmError, match="Failed to parse gh output"):
        await gh.get_pr_checks()


@pytest.mark.asyncio
async def test_github_get_pr_checks_command_error() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(side_effect=ShellError("Fail", CommandResult(1, "", "")))
    gh = AsyncGitHubInterface(shell_executor=mock_shell)

    with pytest.raises(ScmError, match="gh command failed"):
        await gh.get_pr_checks()


@pytest.mark.asyncio
async def test_github_get_latest_run_log_success() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(
        side_effect=[
            CommandResult(0, '[{"databaseId": 123}]', ""),  # list
            CommandResult(0, "Log Content", ""),  # view
        ]
    )
    gh = AsyncGitHubInterface(shell_executor=mock_shell)

    log = await gh.get_latest_run_log("feat")
    assert log == "Log Content"


@pytest.mark.asyncio
async def test_github_get_latest_run_log_no_runs() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(return_value=CommandResult(0, "[]", ""))
    gh = AsyncGitHubInterface(shell_executor=mock_shell)

    log = await gh.get_latest_run_log("feat")
    assert "No workflow runs found" in log


@pytest.mark.asyncio
async def test_github_get_latest_run_log_no_id() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(return_value=CommandResult(0, '[{"databaseId": null}]', ""))
    gh = AsyncGitHubInterface(shell_executor=mock_shell)

    log = await gh.get_latest_run_log("feat")
    assert "Run ID not found" in log


@pytest.mark.asyncio
async def test_github_get_latest_run_log_json_error() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(return_value=CommandResult(0, "invalid json", ""))
    gh = AsyncGitHubInterface(shell_executor=mock_shell)

    with pytest.raises(ScmError, match="Failed to parse run list"):
        await gh.get_latest_run_log("feat")


@pytest.mark.asyncio
async def test_github_get_latest_run_log_error() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(side_effect=ShellError("Fail", CommandResult(1, "", "")))
    gh = AsyncGitHubInterface(shell_executor=mock_shell)

    with pytest.raises(ScmError, match="Failed to fetch run logs"):
        await gh.get_latest_run_log("feat")


# --- AsyncGeminiInterface Tests ---


@pytest.mark.asyncio
async def test_gemini_commands() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(return_value=CommandResult(0, "Scan Output", ""))
    gemini = AsyncGeminiInterface(shell_executor=mock_shell)

    assert await gemini.security_scan() == "Scan Output"
    assert await gemini.code_review() == "Scan Output"


@pytest.mark.asyncio
async def test_gemini_failure() -> None:
    mock_shell = MagicMock(spec=AsyncShellExecutor)
    mock_shell.run = AsyncMock(side_effect=ShellError("Fail", CommandResult(1, "", "")))
    gemini = AsyncGeminiInterface(shell_executor=mock_shell)

    with pytest.raises(ScmError, match="Gemini command failed"):
        await gemini.security_scan()


@pytest.mark.asyncio
async def test_gemini_init_no_executable() -> None:
    with patch("shutil.which", return_value=None):
        with patch("coreason_jules_automator.async_api.scm.logger") as mock_logger:
            AsyncGeminiInterface()
            mock_logger.warning.assert_called()
