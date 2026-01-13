import asyncio
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from coreason_jules_automator.utils.shell import ShellError, ShellExecutor

@pytest.mark.asyncio
async def test_run_async_timeout_check_true() -> None:
    """Test run_async timeout raises ShellError when check=True."""
    shell = ShellExecutor()
    # Mock create_subprocess_exec to simulate timeout
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        process = AsyncMock()

        # When wait_for times out, it cancels the future.
        # But here we are mocking wait_for directly or letting it run?
        # In `shell.py`: await asyncio.wait_for(process.communicate(), timeout=timeout)

        # We need to ensure asyncio.wait_for raises TimeoutError.
        # But we can't easily mock wait_for if it's imported as `asyncio.wait_for` unless we patch asyncio.
        # Alternatively, we can make process.communicate hang.

        async def delayed_communicate():
            await asyncio.sleep(2)
            return (b"", b"")

        process.communicate = delayed_communicate
        process.returncode = 0
        process.kill = MagicMock() # Not async usually?
        # In python 3.12 subprocess.Popen.kill is synchronous.
        # asyncio.subprocess.Process.kill is synchronous.

        mock_exec.return_value = process

        # Use a short timeout
        with pytest.raises(ShellError, match="Command timed out"):
            await shell.run_async(["sleep", "10"], timeout=0.1, check=True)

        process.kill.assert_called_once()

@pytest.mark.asyncio
async def test_run_async_exception_check_true() -> None:
    """Test run_async handles generic exception with check=True."""
    shell = ShellExecutor()
    with patch("asyncio.create_subprocess_exec", side_effect=Exception("Spawn failed")):
        with pytest.raises(ShellError, match="Failed to execute command"):
            await shell.run_async(["cmd"], check=True)

@pytest.mark.asyncio
async def test_run_async_exception_check_false() -> None:
    """Test run_async handles generic exception with check=False."""
    shell = ShellExecutor()
    with patch("asyncio.create_subprocess_exec", side_effect=Exception("Spawn failed")):
        result = await shell.run_async(["cmd"], check=False)
        assert result.exit_code == -1
        assert "Spawn failed" in result.stderr
