import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from pathlib import Path

import pytest

from coreason_jules_automator.async_api.agent import AsyncJulesAgent
from coreason_jules_automator.async_api.shell import AsyncShellExecutor
from coreason_jules_automator.utils.shell import CommandResult
from coreason_jules_automator.llm.types import LLMRequest
from coreason_jules_automator.async_api.llm import AsyncOpenAIAdapter


@pytest.mark.asyncio
async def test_async_shell_executor_run() -> None:
    executor = AsyncShellExecutor()

    # We use new_callable=AsyncMock because create_subprocess_exec is an async function
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        # Use MagicMock for process object
        mock_process = MagicMock()
        # communicate is an async method
        mock_process.communicate = AsyncMock(return_value=(b"stdout", b"stderr"))
        mock_process.returncode = 0

        # When awaited, mock_exec returns mock_process
        mock_exec.return_value = mock_process

        result = await executor.run(["echo", "hello"])

        assert result.exit_code == 0
        assert result.stdout == "stdout"
        assert result.stderr == "stderr"
        mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_async_shell_executor_timeout() -> None:
    executor = AsyncShellExecutor()

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock()
        mock_process.wait = AsyncMock()
        mock_exec.return_value = mock_process

        # We simulate timeout in wait_for
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await executor.run(["sleep", "10"], timeout=1)

            assert result.exit_code == -1
            assert "timed out" in result.stderr
            # kill is synchronous
            mock_process.kill.assert_called()


@pytest.mark.asyncio
async def test_async_jules_agent_launch() -> None:
    with patch("coreason_jules_automator.async_api.agent.get_settings") as mock_settings:
        mock_settings.return_value.repo_name = "test/repo"

        mock_shell = MagicMock(spec=AsyncShellExecutor)
        agent = AsyncJulesAgent(shell=mock_shell)

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_process = MagicMock()
            # Stdin methods
            mock_process.stdin = MagicMock()
            mock_process.stdin.write = MagicMock()
            mock_process.stdin.drain = AsyncMock()

            # Stdout methods
            mock_process.stdout = MagicMock()
            mock_process.stdout.read = AsyncMock()

            # Mock stdout reading sequence
            mock_process.stdout.read.side_effect = [
                b"Do you want to continue? [y/n]",
                b"Session ID: 12345\n100% of the requirements is met",
                b""
            ]

            mock_exec.return_value = mock_process

            # Use AsyncMock for sleep
            with patch("asyncio.sleep", new_callable=AsyncMock):
                sid = await agent.launch_session("Fix the bug")

            assert sid == "12345"
            # Verify auto-reply was sent
            mock_process.stdin.write.assert_called()

            # Check content of writes
            calls = mock_process.stdin.write.call_args_list
            reply_sent = any("Use your best judgment" in str(call[0][0]) for call in calls)
            assert reply_sent

@pytest.mark.asyncio
async def test_async_jules_agent_wait() -> None:
    mock_shell = AsyncMock(spec=AsyncShellExecutor)
    agent = AsyncJulesAgent(shell=mock_shell)

    mock_shell.run.side_effect = [
        CommandResult(0, "12345 running", ""),
        CommandResult(0, "12345 completed", ""),
    ]

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await agent.wait_for_completion("12345")
        assert result is True
        assert mock_shell.run.call_count == 2

@pytest.mark.asyncio
async def test_async_jules_agent_teleport() -> None:
    agent = AsyncJulesAgent()
    target = Path("/tmp/target")

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"stdout", b"stderr"))
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        # We need to mock glob and shutil
        # Since logic runs in asyncio.to_thread, we need to mock where it's executed?
        # to_thread runs the function in a separate thread.
        # Patching objects in the main thread works if the thread shares the same process/memory, which it does.

        with patch.object(Path, "mkdir"):
            # Mock glob to return a fake jules folder
            with patch.object(Path, "glob", return_value=[Path("/tmp/jules_relay_123/jules-source")]):
                with patch("shutil.copytree") as mock_copytree:
                    with patch("shutil.copy2") as mock_copy2:
                        with patch("shutil.rmtree") as mock_rmtree:
                             # We also need to mock Path.exists to return True
                             with patch.object(Path, "exists", return_value=True):
                                result = await agent.teleport_and_sync("123", target)

                                assert result is True
                                mock_exec.assert_called_once()
                                # Check input "y\n" was passed
                                mock_process.communicate.assert_awaited_with(input=b"y\n")
                                mock_copytree.assert_called()

@pytest.mark.asyncio
async def test_async_openai_adapter() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock()
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Hello world"))
    ]

    adapter = AsyncOpenAIAdapter(mock_client, "gpt-4")
    request = LLMRequest(messages=[{"role": "user", "content": "Hi"}], max_tokens=100)

    response = await adapter.execute(request)

    assert response.content == "Hello world"
    mock_client.chat.completions.create.assert_awaited_once_with(
        model="gpt-4",
        messages=request.messages,
        max_tokens=request.max_tokens
    )
