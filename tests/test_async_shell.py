import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coreason_jules_automator.async_api.shell import AsyncShellExecutor
from coreason_jules_automator.utils.shell import ShellError


@pytest.mark.asyncio
async def test_stream_start_process_failure() -> None:
    """Test failure to start the process (e.g. command not found)."""
    executor = AsyncShellExecutor()
    with patch("asyncio.create_subprocess_exec", side_effect=Exception("Start failed")):
        with pytest.raises(ShellError, match="Failed to start process"):
            async for _ in executor.stream(["ls"]):
                pass


@pytest.mark.asyncio
async def test_stream_timeout() -> None:
    """Test process timeout during streaming."""
    executor = AsyncShellExecutor()

    mock_process = MagicMock()
    mock_process.stdout = AsyncMock()
    # Simulate stdout yielding one line
    mock_process.stdout.__aiter__.return_value = iter([b"output line\n"])
    # Simulate wait() raising TimeoutError then returning None (for cleanup)
    mock_process.wait = AsyncMock(side_effect=[asyncio.TimeoutError, None])
    mock_process.kill = MagicMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with pytest.raises(ShellError, match="Command timed out"):
            async for _ in executor.stream(["ls"], timeout=1):
                pass

    mock_process.kill.assert_called_once()
    mock_process.wait.assert_awaited()


@pytest.mark.asyncio
async def test_stream_non_zero_exit() -> None:
    """Test process returning non-zero exit code."""
    executor = AsyncShellExecutor()

    mock_process = MagicMock()
    mock_process.stdout = AsyncMock()
    mock_process.stdout.__aiter__.return_value = iter([])
    mock_process.wait = AsyncMock(return_value=None)
    mock_process.returncode = 1
    mock_process.stderr = AsyncMock()
    mock_process.stderr.read = AsyncMock(return_value=b"Error output")

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with pytest.raises(ShellError, match="Command failed with exit code 1"):
            async for _ in executor.stream(["ls"]):
                pass


@pytest.mark.asyncio
async def test_stream_generic_exception() -> None:
    """Test generic exception during streaming/waiting."""
    executor = AsyncShellExecutor()

    mock_process = MagicMock()
    mock_process.stdout = AsyncMock()
    mock_process.stdout.__aiter__.return_value = iter([])
    # Fail first time, succeed second time (cleanup)
    mock_process.wait = AsyncMock(side_effect=[Exception("Generic error"), None])
    mock_process.returncode = None  # To trigger cleanup
    mock_process.kill = MagicMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        with pytest.raises(ShellError, match="Stream execution failed: Generic error"):
            async for _ in executor.stream(["ls"]):
                pass

    mock_process.kill.assert_called_once()
    mock_process.wait.assert_awaited()
