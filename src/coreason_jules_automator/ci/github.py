import json
import shutil
from typing import Any, Dict, List, Optional

from coreason_jules_automator.utils.logger import logger
from coreason_jules_automator.utils.shell import ShellError, ShellExecutor


class GitHubInterface:
    """
    Interface for interacting with the GitHub CLI (gh).
    Implements 'Line 2' of the defense strategy (Remote CI/CD Verification).
    """

    def __init__(self, shell_executor: Optional[ShellExecutor] = None) -> None:
        self.executable = "gh"
        self.shell = shell_executor or ShellExecutor()
        if not shutil.which(self.executable):
            logger.warning(f"GitHub CLI executable '{self.executable}' not found in PATH.")

    def _run_command(self, args: List[str]) -> str:
        """
        Executes a gh command.

        Args:
            args: List of arguments to pass to the gh command.

        Returns:
            The standard output of the command if successful.

        Raises:
            RuntimeError: If the command fails (non-zero exit code).
        """
        command = [self.executable] + args
        try:
            result = self.shell.run(command, check=True)
            return result.stdout.strip()
        except ShellError as e:
            logger.error(str(e))
            raise RuntimeError(f"gh command failed: {e}") from e

    def get_pr_checks(self) -> List[Dict[str, Any]]:
        """
        Polls GitHub Actions status for the current PR.
        Uses `gh pr checks` to get the status.

        Returns:
            A list containing the checks status.
        """
        logger.info("Polling PR checks...")
        # using --json to get structured data
        output = self._run_command(["pr", "checks", "--json", "bucket,name,status,conclusion,url"])
        try:
            # We explicitly type the result of json.loads
            parsed: Any = json.loads(output)
            if not isinstance(parsed, list):
                raise RuntimeError(f"Unexpected format from gh: expected list, got {type(parsed)}")
            # We assume it's a list of dicts based on gh documentation
            return parsed
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse gh output: {output}") from e
