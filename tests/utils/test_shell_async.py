import pytest

from coreason_jules_automator.utils.shell import ShellExecutor


@pytest.mark.asyncio
async def test_run_async_success() -> None:
    """Test successful async execution of a command."""
    shell = ShellExecutor()
    result = await shell.run_async(["echo", "hello"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "hello"
    assert result.stderr == ""


@pytest.mark.asyncio
async def test_run_async_failure_check_false() -> None:
    """Test async execution failure when check=False."""
    shell = ShellExecutor()
    # Assuming 'ls /nonexistent' fails with non-zero exit code
    result = await shell.run_async(["ls", "/nonexistent"], check=False)

    assert result.exit_code != 0
    assert "No such file or directory" in result.stderr or result.stderr != ""


@pytest.mark.asyncio
async def test_run_async_timeout() -> None:
    """Test async execution timeout."""
    shell = ShellExecutor()
    # Sleep for 2 seconds, but timeout is 1 second
    result = await shell.run_async(["sleep", "2"], timeout=1)

    assert result.exit_code == -1
    assert "timed out" in result.stderr


@pytest.mark.asyncio
async def test_run_async_not_found() -> None:
    """Test async execution of non-existent command."""
    shell = ShellExecutor()
    result = await shell.run_async(["nonexistentcommand123"], check=False)

    assert result.exit_code == -1
    assert "No such file or directory" in result.stderr or "not found" in result.stderr.lower()
