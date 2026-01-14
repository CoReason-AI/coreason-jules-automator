import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coreason_jules_automator.async_api.agent import AsyncJulesAgent
from coreason_jules_automator.async_api.llm import AsyncOpenAIAdapter
from coreason_jules_automator.async_api.shell import AsyncShellExecutor
from coreason_jules_automator.llm.types import LLMRequest
from coreason_jules_automator.utils.shell import CommandResult, ShellError


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
            mock_process.stdout.read = AsyncMock()

            # Mock stdout reading sequence
            mock_process.stdout.read.side_effect = [
                b"Do you want to continue? [y/n]",
                b"Session ID: 12345\n100% of the requirements is met",
                b"",
            ]
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

            # Check content of writes
            calls = mock_process.stdin.write.call_args_list
            reply_sent = any("Use your best judgment" in str(call[0][0]) for call in calls)
            assert reply_sent

            # Verify SPEC.md context was included
            context_sent = any("Spec Content" in str(call[0][0]) for call in calls)
            assert context_sent

@pytest.mark.asyncio
async def test_async_jules_agent_launch_failure() -> None:
    agent = AsyncJulesAgent()
    with patch("coreason_jules_automator.async_api.agent.get_settings"):
        with patch("asyncio.create_subprocess_exec", side_effect=Exception("Launch failed")):
            sid = await agent.launch_session("task")
            assert sid is None

@pytest.mark.asyncio
async def test_async_jules_agent_launch_stdin_error() -> None:
    agent = AsyncJulesAgent()
    with patch("coreason_jules_automator.async_api.agent.get_settings"):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_process = MagicMock()
            mock_process.stdin = MagicMock()
            mock_process.stdin.write.side_effect = Exception("Write failed")
            mock_process.stdout = MagicMock()
            mock_process.stdout.read = AsyncMock(return_value=b"") # EOF immediately
            mock_process.returncode = 0
            mock_process.wait = AsyncMock()
            mock_exec.return_value = mock_process

            with patch("asyncio.sleep", new_callable=AsyncMock):
                sid = await agent.launch_session("task")
            assert sid is None
            # Stdin write was attempted
            mock_process.stdin.write.assert_called()

@pytest.mark.asyncio
async def test_async_jules_agent_launch_no_stdout() -> None:
    agent = AsyncJulesAgent()
    with patch("coreason_jules_automator.async_api.agent.get_settings"):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_process = MagicMock()
            mock_process.stdin = MagicMock()
            mock_process.stdout = None # No stdout
            mock_process.returncode = 0
            mock_process.wait = AsyncMock()
            mock_exec.return_value = mock_process

            with patch("asyncio.sleep", new_callable=AsyncMock):
                sid = await agent.launch_session("task")
            assert sid is None

@pytest.mark.asyncio
async def test_async_jules_agent_launch_cleanup_no_timeout() -> None:
    # Test cleanup when loop breaks but process is still running (e.g. EOF)
    agent = AsyncJulesAgent()
    with patch("coreason_jules_automator.async_api.agent.get_settings"):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_process = MagicMock()
            mock_process.stdin = MagicMock()
            mock_process.stdout = MagicMock()
            mock_process.stdout.read = AsyncMock(return_value=b"") # EOF
            mock_process.returncode = None # Still running
            mock_process.terminate = MagicMock()
            mock_process.wait = AsyncMock() # Wait succeeds
            mock_exec.return_value = mock_process

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await agent.launch_session("task")

            mock_process.terminate.assert_called()
            mock_process.wait.assert_called()

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
async def test_async_jules_agent_launch_loop_timeout() -> None:
    agent = AsyncJulesAgent()
    with patch("coreason_jules_automator.async_api.agent.get_settings"):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_process = MagicMock()
            mock_process.stdin = MagicMock()
            mock_process.stdin.drain = AsyncMock()
            mock_process.stdout = MagicMock()

            # Read always timeouts
            mock_process.stdout.read.side_effect = asyncio.TimeoutError
            mock_process.returncode = None
            mock_process.terminate = MagicMock()
            mock_process.kill = MagicMock()
            mock_process.wait = AsyncMock()
            mock_exec.return_value = mock_process

            # Mock loop time to simulate timeout
            mock_loop = MagicMock()
            mock_loop.time.side_effect = [0] + [10]*50 + [2000]

            with patch("asyncio.get_running_loop", return_value=mock_loop):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    with patch.object(agent, "_cleanup_process", new_callable=AsyncMock) as mock_cleanup:
                        sid = await agent.launch_session("task")
                        mock_cleanup.assert_awaited_once_with(mock_process)

            assert sid is None

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
async def test_async_jules_agent_wait_failures() -> None:
    mock_shell = AsyncMock(spec=AsyncShellExecutor)
    agent = AsyncJulesAgent(shell=mock_shell)

    # Case 1: SID disappeared
    mock_shell.run.return_value = CommandResult(0, "other_sid running", "")
    with patch("asyncio.sleep", new_callable=AsyncMock):
        assert await agent.wait_for_completion("123") is False

    # Case 2: Failed status
    mock_shell.run.return_value = CommandResult(0, "123 failed", "")
    with patch("asyncio.sleep", new_callable=AsyncMock):
        assert await agent.wait_for_completion("123") is False

    # Case 3: Exception during run
    mock_shell.run.side_effect = [Exception("Error"), CommandResult(0, "123 completed", "")]
    with patch("asyncio.sleep", new_callable=AsyncMock):
        assert await agent.wait_for_completion("123") is True

    # Case 4: Timeout
    mock_shell.run.side_effect = None
    mock_shell.run.return_value = CommandResult(0, "123 running", "")
    mock_loop = MagicMock()
    mock_loop.time.side_effect = [0, 2000] # Trigger timeout
    with patch("asyncio.get_running_loop", return_value=mock_loop):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            assert await agent.wait_for_completion("123") is False


@pytest.mark.asyncio
async def test_async_jules_agent_teleport() -> None:
    agent = AsyncJulesAgent()
    target = Path("/tmp/target")

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"stdout", b"stderr"))
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        with patch.object(Path, "mkdir"):
            # Mock glob to return a fake jules folder
            with patch.object(Path, "glob", return_value=[Path("/tmp/jules_relay_123/jules-source")]):
                with patch("shutil.copytree") as mock_copytree:
                    with patch("shutil.copy2"):
                        with patch("shutil.rmtree"):
                            # We also need to mock Path.exists to return True
                            with patch.object(Path, "exists", return_value=True):
                                result = await agent.teleport_and_sync("123", target)

                                assert result is True
                                mock_exec.assert_called_once()
                                # Check input "y\n" was passed
                                mock_process.communicate.assert_awaited_with(input=b"y\n")
                                mock_copytree.assert_called()

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
        with patch.object(Path, "mkdir"):
            with patch("shutil.rmtree"):
                 assert await agent.teleport_and_sync("123", target) is False

    # Case 2: Sync failed (no folder)
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0
        mock_exec.return_value = mock_process
        with patch.object(Path, "mkdir"):
            with patch.object(Path, "glob", return_value=[]):
                 with patch("shutil.rmtree"):
                     assert await agent.teleport_and_sync("123", target) is False

    # Case 3: Exception
    with patch("asyncio.create_subprocess_exec", side_effect=Exception("Fail")):
         with patch.object(Path, "mkdir"):
             with patch("shutil.rmtree"):
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
