import json
import shutil
import subprocess
from typing import Any, Dict, List

from coreason_jules_automator.utils.logger import logger


class GitHubInterface:
    """
    Interface for interacting with the GitHub CLI (gh).
    Implements 'Line 2' of the defense strategy (Remote CI/CD Verification).
    """

    def __init__(self, executable: str = "gh") -> None:
        self.executable = executable
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
        logger.debug(f"Executing: {' '.join(command)}")

        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except Exception as e:
            raise RuntimeError(f"Failed to execute gh command: {e}") from e

        if result.returncode != 0:
            error_msg = (
                f"gh command failed (Exit {result.returncode}):\n{result.stderr.strip() or result.stdout.strip()}"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        return str(result.stdout.strip())

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

    def push_to_branch(self, branch_name: str, message: str) -> None:
        """
        Pushes changes to a specific branch.
        Note: This usually uses `git` directly, but we can also use gh for PR creation.
        Since the spec asks to wrap `gh`, and `gh` interacts with PRs, we'll assume
        git operations are handled via git CLI or this wrapper needs to handle git push too.

        However, `gh` does not replace `git push`.
        The spec says: "Push to a task branch" and "wraps gh CLI".
        We will implement `git` push wrapping here for convenience, or assume `gh pr create` workflow.

        Let's implement a generic git push wrapper here as it's part of the CI loop.
        """
        logger.info(f"Pushing to branch {branch_name}")
        # Using git directly for push as gh doesn't do it.
        try:
            subprocess.run(["git", "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", message], check=True, capture_output=True)
            subprocess.run(["git", "push", "origin", branch_name], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            # Captured output is bytes, so we decode it. stderr might be None.
            error_output = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"Git push failed: {error_output}")
            # Include the output in the raised error so it can be asserted on
            raise RuntimeError(f"Git push failed: {error_output}") from e
