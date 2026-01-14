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

    def get_latest_run_log(self, branch_name: str) -> str:
        """
        Fetches the log of the latest workflow run for the given branch.
        """
        logger.info(f"Fetching latest run logs for branch: {branch_name}")
        try:
            # 1. Get the latest run ID
            output = self._run_command(["run", "list", "--branch", branch_name, "--limit", "1", "--json", "databaseId"])
            runs = json.loads(output)

            if not runs or not isinstance(runs, list):
                logger.warning(f"No runs found for branch {branch_name}")
                return "No workflow runs found."

            # runs[0] can be a dict
            run_id_val = runs[0].get("databaseId")
            if run_id_val is None:
                logger.warning("Run ID not found in response.")
                return "Run ID not found."
            run_id = str(run_id_val)

            # 2. Get the log
            log_output = self._run_command(["run", "view", run_id, "--log"])
            return log_output

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse gh output: {e}")
            return f"Failed to parse run list: {e}"
        except Exception as e:
            logger.error(f"Failed to fetch run logs: {e}")
            return f"Failed to fetch run logs: {e}"
