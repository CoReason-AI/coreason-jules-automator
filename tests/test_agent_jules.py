import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch
import pexpect
import pytest
from coreason_jules_automator.agent.jules import JulesAgent

@pytest.fixture
def agent() -> JulesAgent:
    return JulesAgent()

@patch("subprocess.run")
def test_get_active_sids(mock_run: MagicMock, agent: JulesAgent) -> None:
    mock_run.return_value.stdout = "123 active\n456 completed"
    sids = agent._get_active_sids()
    assert "123" in sids
    assert "456" in sids
    assert len(sids) == 2

@patch("subprocess.run")
def test_get_active_sids_empty(mock_run: MagicMock, agent: JulesAgent) -> None:
    mock_run.return_value.stdout = "No sessions found"
    sids = agent._get_active_sids()
    assert len(sids) == 0

@patch("subprocess.run")
def test_get_active_sids_failure(mock_run: MagicMock, agent: JulesAgent) -> None:
    mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
    sids = agent._get_active_sids()
    assert sids == set()

@patch("pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_success(
    mock_settings: MagicMock,
    mock_get_sids: MagicMock,
    mock_spawn: MagicMock,
    agent: JulesAgent,
) -> None:
    mock_settings.return_value.repo_name = "test/repo"

    # Mock pexpect child
    mock_child = MagicMock()
    mock_spawn.return_value = mock_child
    mock_child.isalive.return_value = False # For cleanup check

    # Mock expect to return TIMEOUT then SIDs check finds something
    # expect returns index
    # 0: Question, 1: Success, 2: EOF, 3: TIMEOUT

    # Sequence:
    # 1. Expect -> TIMEOUT (index 3)
    # 2. _get_active_sids called -> finds new SID
    # 3. Break

    mock_child.expect.return_value = 3
    mock_get_sids.side_effect = [{"100"}, {"100", "101"}]

    with patch("time.sleep", return_value=None):
        sid = agent.launch_session("Test Task")

    assert sid == "101"
    mock_spawn.assert_called_once()
    mock_child.sendline.assert_called()
    mock_child.close.assert_called_once()

@patch("pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_auto_reply(
    mock_settings: MagicMock,
    mock_get_sids: MagicMock,
    mock_spawn: MagicMock,
    agent: JulesAgent,
) -> None:
    mock_settings.return_value.repo_name = "test/repo"
    mock_child = MagicMock()
    mock_spawn.return_value = mock_child
    mock_child.isalive.return_value = False

    # Sequence:
    # 1. Expect -> Question (index 0)
    # 2. Expect -> TIMEOUT (index 3) -> Check SIDs -> Success

    mock_child.expect.side_effect = [0, 3]
    mock_child.after = "Continue? [y/n]"

    mock_get_sids.side_effect = [{"100"}, {"100", "101"}]

    with patch("time.sleep", return_value=None):
        sid = agent.launch_session("Test Task")

    assert sid == "101"
    # Verify auto-reply sent
    mock_child.sendline.assert_any_call("Use your best judgment and make autonomous decisions.")

@patch("pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_mission_complete(
    mock_settings: MagicMock,
    mock_get_sids: MagicMock,
    mock_spawn: MagicMock,
    agent: JulesAgent,
) -> None:
    mock_settings.return_value.repo_name = "test/repo"
    mock_child = MagicMock()
    mock_spawn.return_value = mock_child
    mock_child.isalive.return_value = False

    # Sequence:
    # 1. Expect -> Success (index 1)
    # 2. Expect -> TIMEOUT (index 3) -> Check SIDs -> Success

    mock_child.expect.side_effect = [1, 3]
    mock_get_sids.side_effect = [{"100"}, {"100", "101"}]

    with patch("time.sleep", return_value=None):
        sid = agent.launch_session("Test Task")

    assert sid == "101"
    assert agent.mission_complete is True

@patch("pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_timeout(
    mock_settings: MagicMock,
    mock_get_sids: MagicMock,
    mock_spawn: MagicMock,
    agent: JulesAgent,
) -> None:
    mock_settings.return_value.repo_name = "test/repo"
    mock_child = MagicMock()
    mock_spawn.return_value = mock_child
    mock_child.isalive.return_value = True # Process still running

    mock_get_sids.return_value = {"100"}
    mock_child.expect.return_value = 3 # Always timeout

    # Loop should break on global timeout
    # We simulate time passing
    with patch("time.time", side_effect=[0, 1801, 1801, 1801]): # Need enough side effects
         sid = agent.launch_session("Test Task")

    assert sid is None
    mock_child.terminate.assert_called_with(force=True)
    mock_child.close.assert_called()

@patch("pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_eof(
    mock_settings: MagicMock,
    mock_get_sids: MagicMock,
    mock_spawn: MagicMock,
    agent: JulesAgent,
) -> None:
    mock_settings.return_value.repo_name = "test/repo"
    mock_child = MagicMock()
    mock_spawn.return_value = mock_child

    # Sequence: Expect -> EOF (index 2)
    mock_child.expect.return_value = 2
    mock_get_sids.return_value = {"100"}

    sid = agent.launch_session("Test Task")

    assert sid is None
    mock_child.close.assert_called()

@patch("pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_with_spec(
    mock_settings: MagicMock,
    mock_get_sids: MagicMock,
    mock_spawn: MagicMock,
    agent: JulesAgent,
) -> None:
    mock_settings.return_value.repo_name = "test/repo"
    mock_child = MagicMock()
    mock_spawn.return_value = mock_child
    mock_child.isalive.return_value = False

    mock_child.expect.return_value = 3
    mock_get_sids.side_effect = [{"100"}, {"100", "101"}]

    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.read_text", return_value="Spec Content"):
             with patch("time.sleep", return_value=None):
                sid = agent.launch_session("Test Task")

    assert sid == "101"
    mock_child.sendline.assert_called()
    call_args = mock_child.sendline.call_args[0][0]
    assert "Context from SPEC.md" in call_args
    assert "Spec Content" in call_args

@patch("pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_success_with_cleanup(
    mock_settings: MagicMock,
    mock_get_sids: MagicMock,
    mock_spawn: MagicMock,
    agent: JulesAgent,
) -> None:
    mock_settings.return_value.repo_name = "test/repo"
    mock_child = MagicMock()
    mock_spawn.return_value = mock_child
    mock_child.isalive.return_value = True # Needs cleanup

    mock_child.expect.return_value = 3
    mock_get_sids.side_effect = [{"100"}, {"100", "101"}]

    with patch("time.sleep", return_value=None):
        sid = agent.launch_session("Test Task")

    assert sid == "101"
    mock_child.terminate.assert_called_with(force=True)

@patch("pexpect.spawn")
@patch("coreason_jules_automator.agent.jules.JulesAgent._get_active_sids")
@patch("coreason_jules_automator.agent.jules.get_settings")
def test_launch_session_exception(
    mock_settings: MagicMock,
    mock_get_sids: MagicMock,
    mock_spawn: MagicMock,
    agent: JulesAgent,
) -> None:
    mock_settings.return_value.repo_name = "test/repo"
    mock_spawn.side_effect = Exception("Launch Error")

    sid = agent.launch_session("Test Task")
    assert sid is None

# Keeping existing tests for wait_for_completion and teleport_and_sync as they use subprocess
@patch("subprocess.run")
def test_wait_for_completion_success(mock_run: MagicMock, agent: JulesAgent) -> None:
    mock_run.side_effect = [
        MagicMock(stdout="123 running"),
        MagicMock(stdout="123 completed"),
    ]
    with patch("time.sleep", return_value=None):
        result = agent.wait_for_completion("123")
    assert result is True

@patch("subprocess.run")
def test_wait_for_completion_failed(mock_run: MagicMock, agent: JulesAgent) -> None:
    mock_run.return_value.stdout = "123 failed error"
    with patch("time.sleep", return_value=None):
        result = agent.wait_for_completion("123")
    assert result is False

@patch("subprocess.run")
def test_wait_for_completion_disappeared(mock_run: MagicMock, agent: JulesAgent) -> None:
    mock_run.return_value.stdout = "456 running"
    with patch("time.sleep", return_value=None):
        result = agent.wait_for_completion("123")
    assert result is False

@patch("subprocess.run")
def test_wait_for_completion_exception(mock_run: MagicMock, agent: JulesAgent) -> None:
    mock_run.side_effect = [
        Exception("Network Error"),
        MagicMock(stdout="123 completed"),
    ]
    with patch("time.sleep", return_value=None):
        with patch("time.time", return_value=0):
            result = agent.wait_for_completion("123")
    assert result is True

@patch("subprocess.run")
def test_wait_for_completion_timeout(mock_run: MagicMock, agent: JulesAgent) -> None:
    mock_run.return_value.stdout = "123 running"
    with patch("time.time", side_effect=[0, 1801, 1801]):
        with patch("time.sleep", return_value=None):
            result = agent.wait_for_completion("123")
    assert result is False

@patch("subprocess.run")
@patch("shutil.copytree")
@patch("shutil.copy2")
@patch("pathlib.Path.mkdir")
@patch("shutil.rmtree")
def test_teleport_and_sync_success(
    mock_rmtree: MagicMock,
    mock_mkdir: MagicMock,
    mock_copy2: MagicMock,
    mock_copytree: MagicMock,
    mock_run: MagicMock,
    agent: JulesAgent,
) -> None:
    mock_run.return_value = MagicMock()
    with patch("pathlib.Path.glob", return_value=[MagicMock(name="jules-123")]):
        with patch("pathlib.Path.exists", return_value=True):
            result = agent.teleport_and_sync("123", Path("/tmp"))
    assert result is True
    assert mock_copy2.call_count >= 1

@patch("subprocess.run")
@patch("pathlib.Path.mkdir")
def test_teleport_and_sync_no_folder(mock_mkdir: MagicMock, mock_run: MagicMock, agent: JulesAgent) -> None:
    mock_run.return_value = MagicMock()
    with patch("pathlib.Path.glob", return_value=[]):
        result = agent.teleport_and_sync("123", Path("/tmp"))
    assert result is False

@patch("subprocess.run")
def test_teleport_and_sync_failure(mock_run: MagicMock, agent: JulesAgent) -> None:
    mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="error")
    with patch("pathlib.Path.mkdir"):
        result = agent.teleport_and_sync("123", Path("/tmp"))
    assert result is False

@patch("subprocess.run")
@patch("pathlib.Path.mkdir")
def test_teleport_and_sync_exception(mock_mkdir: MagicMock, mock_run: MagicMock, agent: JulesAgent) -> None:
    mock_run.side_effect = Exception("Disk Error")
    result = agent.teleport_and_sync("123", Path("/tmp"))
    assert result is False
