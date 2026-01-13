from unittest.mock import MagicMock, patch

import pytest
from coreason_jules_automator.utils.shell import ShellError, ShellExecutor


def test_run_failure_stdout_only() -> None:
    """Test command failure with stdout only (no stderr)."""
    shell = ShellExecutor()
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "Output with error"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        with pytest.raises(ShellError) as excinfo:
            shell.run(["test"], check=True)

        assert "Command failed with exit code 1: Output with error" in str(excinfo.value)
