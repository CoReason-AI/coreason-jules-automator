import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coreason_jules_automator.async_api.agent import AsyncJulesAgent
from coreason_jules_automator.async_api.llm import AsyncOpenAIAdapter
from coreason_jules_automator.async_api.shell import AsyncShellExecutor
from coreason_jules_automator.llm.types import LLMRequest
from coreason_jules_automator.utils.shell import ShellError


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
            # Check=False to verify result content
            result = await executor.run(["sleep", "10"], timeout=1, check=False)

            assert result.exit_code == -1
            assert "timed out" in result.stderr
            # kill is synchronous
            mock_process.kill.assert_called()


@pytest.mark.asyncio
async def test_async_shell_executor_timeout_check_true() -> None:
    executor = AsyncShellExecutor()

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock()
        mock_process.wait = AsyncMock()
        mock_exec.return_value = mock_process

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            with pytest.raises(ShellError) as exc:
                await executor.run(["sleep", "10"], timeout=1, check=True)
            assert "Command timed out" in str(exc.value)
            mock_process.kill.assert_called()


@pytest.mark.asyncio
async def test_async_shell_executor_exception() -> None:
    executor = AsyncShellExecutor()

    with patch("asyncio.create_subprocess_exec", side_effect=Exception("Boom")):
        # Check=False to verify result content
        result = await executor.run(["echo", "fail"], check=False)
        assert result.exit_code == -1
        assert "Boom" in result.stderr


@pytest.mark.asyncio
async def test_async_shell_executor_exception_check_true() -> None:
    executor = AsyncShellExecutor()

    with patch("asyncio.create_subprocess_exec", side_effect=Exception("Boom")):
        with pytest.raises(ShellError) as exc:
            await executor.run(["echo", "fail"], check=True)
        assert "Failed to execute command" in str(exc.value)
        assert "Boom" in str(exc.value)


@pytest.mark.asyncio
async def test_async_shell_executor_check_failure() -> None:
    executor = AsyncShellExecutor()
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"error"))
        mock_process.returncode = 1
        mock_exec.return_value = mock_process

        with pytest.raises(ShellError) as exc:
            await executor.run(["fail"], check=True)
        assert "Command failed" in str(exc.value)
        assert "error" in str(exc.value)


@pytest.mark.asyncio
async def test_async_shell_executor_check_failure_stdout() -> None:
    executor = AsyncShellExecutor()
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"out", b""))
        mock_process.returncode = 1
        mock_exec.return_value = mock_process

        with pytest.raises(ShellError) as exc:
            await executor.run(["fail"], check=True)
        assert "Command failed" in str(exc.value)
        assert "out" in str(exc.value)


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
            # The agent uses `await process.stdout.readline()`, NOT `read()`.
            # We must mock `readline`.
            mock_process.stdout.readline = AsyncMock(
                side_effect=[
                    b"Do you want to continue? [y/n]\n",
                    b"Session ID: 12345\n",
                    b"100% of the requirements is met\n",
                    b"",
                ]
            )
            mock_process.returncode = 0
            mock_process.wait = AsyncMock()

            mock_exec.return_value = mock_process

            # Mock SPEC.md existence
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "read_text", return_value="Spec Content"):
                    # Use AsyncMock for sleep
                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        sid = await agent.launch_session("Fix the bug")

            assert sid == "12345"
            # Verify auto-reply was sent
            mock_process.stdin.write.assert_called()


@pytest.mark.asyncio
async def test_async_jules_agent_launch_failure() -> None:
    agent = AsyncJulesAgent()
    with patch("coreason_jules_automator.async_api.agent.get_settings"):
        with patch("asyncio.create_subprocess_exec", side_effect=Exception("Launch failed")):
            sid = await agent.launch_session("task")
            assert sid is None


@pytest.mark.asyncio
async def test_async_jules_agent_launch_no_stdout() -> None:
    agent = AsyncJulesAgent()
    with patch("coreason_jules_automator.async_api.agent.get_settings"):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_process = MagicMock()
            mock_process.stdin = MagicMock()
            mock_process.stdout = None  # No stdout
            mock_process.returncode = 0
            mock_process.wait = AsyncMock()
            mock_exec.return_value = mock_process

            with patch("asyncio.sleep", new_callable=AsyncMock):
                sid = await agent.launch_session("task")
            assert sid is None


@pytest.mark.asyncio
async def test_async_jules_agent_cleanup_process() -> None:
    agent = AsyncJulesAgent()

    # Case 1: Process running, terminates cleanly
    mock_process = MagicMock()
    mock_process.returncode = None
    mock_process.terminate = MagicMock()
    mock_process.wait = AsyncMock()

    await agent._cleanup_process(mock_process)
    mock_process.terminate.assert_called_once()
    mock_process.wait.assert_awaited_once()
    mock_process.kill.assert_not_called()

    # Case 2: Process running, wait times out
    mock_process = MagicMock()
    mock_process.returncode = None
    mock_process.terminate = MagicMock()
    # Mock wait() to be awaitable
    mock_process.wait = AsyncMock()

    # We patch wait_for to raise TimeoutError
    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
        await agent._cleanup_process(mock_process)

    mock_process.terminate.assert_called_once()
    mock_process.kill.assert_called_once()

    # Case 3: Process already done
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.terminate = MagicMock()

    await agent._cleanup_process(mock_process)
    mock_process.terminate.assert_not_called()


@pytest.mark.asyncio
async def test_async_jules_agent_launch_monitor_exception() -> None:
    agent = AsyncJulesAgent()
    with patch("coreason_jules_automator.async_api.agent.get_settings"):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_process = MagicMock()
            mock_process.stdout = MagicMock()
            # Raise exception during readline
            mock_process.stdout.readline = AsyncMock(side_effect=Exception("Read error"))
            mock_process.returncode = None
            mock_process.kill = MagicMock()
            # Ensure wait is awaitable
            mock_process.wait = AsyncMock()

            mock_exec.return_value = mock_process

            sid = await agent.launch_session("task")
            assert sid is None
            # Terminate called via exception handler
            mock_process.terminate.assert_called()


@pytest.mark.asyncio
async def test_async_jules_agent_wait() -> None:
    # Test wait_for_completion reading from process stdout
    agent = AsyncJulesAgent()

    # Mock the internal process object as if launch_session created it
    mock_process = MagicMock()
    mock_process.returncode = None
    mock_process.stdout = MagicMock()
    # Read sequence: success signal then EOF
    mock_process.stdout.readline = AsyncMock(
        side_effect=[b"Processing...\n", b"100% of the requirements is met\n", b""]
    )

    agent.process = mock_process

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await agent.wait_for_completion("123")
        assert result is True


@pytest.mark.asyncio
async def test_async_jules_agent_wait_eof() -> None:
    # Test wait_for_completion encountering EOF without success
    agent = AsyncJulesAgent()

    mock_process = MagicMock()
    mock_process.returncode = 0  # Exited
    mock_process.stdout = MagicMock()
    mock_process.stdout.readline = AsyncMock(return_value=b"")  # EOF

    agent.process = mock_process

    result = await agent.wait_for_completion("123")
    # Should be False as mission_complete was never set
    assert result is False


@pytest.mark.asyncio
async def test_async_jules_agent_wait_exception() -> None:
    agent = AsyncJulesAgent()

    mock_process = MagicMock()
    mock_process.returncode = None
    mock_process.stdout = MagicMock()
    mock_process.stdout.readline = AsyncMock(side_effect=Exception("Stream Error"))

    agent.process = mock_process

    result = await agent.wait_for_completion("123")
    assert result is False


@pytest.mark.asyncio
async def test_async_jules_agent_teleport() -> None:
    agent = AsyncJulesAgent()
    target = Path("/tmp/target")

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"stdout", b"stderr"))
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        result = await agent.teleport_and_sync("123", target)

        assert result is True
        mock_exec.assert_called_once()
        # Ensure command args include teleport
        args = mock_exec.call_args[0]
        assert "teleport" in args


@pytest.mark.asyncio
async def test_async_jules_agent_teleport_failures() -> None:
    agent = AsyncJulesAgent()
    target = Path("/tmp/target")

    # Case 1: Command failed
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"error"))
        mock_process.returncode = 1
        mock_exec.return_value = mock_process

        assert await agent.teleport_and_sync("123", target) is False


@pytest.mark.asyncio
async def test_async_openai_adapter() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock()
    mock_client.chat.completions.create.return_value.choices = [MagicMock(message=MagicMock(content="Hello world"))]

    adapter = AsyncOpenAIAdapter(mock_client, "gpt-4")
    request = LLMRequest(messages=[{"role": "user", "content": "Hi"}], max_tokens=100)

    response = await adapter.execute(request)

    assert response.content == "Hello world"
    mock_client.chat.completions.create.assert_awaited_once_with(
        model="gpt-4", messages=request.messages, max_tokens=request.max_tokens
    )
