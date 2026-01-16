import json
import shutil
from typing import Any, Dict, List, NoReturn, Optional

from coreason_jules_automator.async_api.shell import AsyncShellExecutor
from coreason_jules_automator.exceptions import AuthError, NetworkError, ScmError
from coreason_jules_automator.utils.logger import logger
from coreason_jules_automator.utils.shell import ShellError


def _handle_shell_error(e: ShellError, context: str) -> NoReturn:
    """Helper to map ShellError to specific domain exceptions."""
    msg = (str(e) + " " + e.result.stderr).lower()
    if any(x in msg for x in ["timed out", "could not resolve host", "failed to connect", "connection refused"]):
        raise NetworkError(f"{context}: {e}") from e
    if any(x in msg for x in ["permission denied", "403", "authentication failed"]):
        raise AuthError(f"{context}: {e}") from e
    raise ScmError(f"{context}: {e}") from e


class AsyncGitInterface:
    """
    Async interface for interacting with the git CLI.
    """

    def __init__(self, shell_executor: Optional[AsyncShellExecutor] = None) -> None:
        self.shell = shell_executor or AsyncShellExecutor()

    async def has_changes(self) -> bool:
        """
        Checks if there are any changes in the git repository.

        Returns:
            True if there are changes, False otherwise.
        """
        try:
            result = await self.shell.run(["git", "status", "--porcelain"], check=True)
            return bool(result.stdout.strip())
        except ShellError as e:
            logger.error(f"Git status check failed: {e}")
            return False

    async def push_to_branch(self, branch_name: str, message: str) -> bool:
        """
        Pushes changes to a specific branch.

        Args:
            branch_name: The name of the branch to push to.
            message: The commit message.

        Returns:
            True if changes were pushed, False if no changes were detected.

        Raises:
            RuntimeError: If any git command fails.
        """
        logger.info(f"Preparing to push to branch {branch_name}")
        try:
            # 1. Clear stale locks
            await self.shell.run(["rm", "-f", ".git/index.lock"], check=False)

            # 2. Add changes
            await self.shell.run(["git", "add", "."], check=True)

            # 3. Check for changes
            if not await self.has_changes():
                logger.warning("⚠️ No changes detected. Skipping commit and push.")
                return False

            # 4. Commit and Push
            await self.shell.run(["git", "commit", "-m", message], check=True)
            await self.shell.run(["git", "push", "origin", branch_name], check=True)
            return True

        except ShellError as e:
            logger.error(f"Git push failed: {e}")
            _handle_shell_error(e, "Git push failed")

    async def checkout_new_branch(self, branch_name: str, base_branch: str, pull_base: bool = True) -> None:
        """
        Creates and checks out a new branch from a base branch.
        """
        try:
            # Check out base first to ensure we are clean/up-to-date
            await self.shell.run(["git", "checkout", base_branch], check=True)
            if pull_base:
                await self.shell.run(["git", "pull", "origin", base_branch], check=True)
            # Create new branch
            await self.shell.run(["git", "checkout", "-b", branch_name], check=True)
        except ShellError as e:
            logger.error(f"Failed to checkout new branch {branch_name} from {base_branch}: {e}")
            _handle_shell_error(e, "Failed to checkout new branch")

    async def merge_squash(self, source_branch: str, target_branch: str, message: str) -> None:
        """
        Squash merges source_branch into target_branch with a custom message.
        """
        try:
            await self.shell.run(["git", "checkout", target_branch], check=True)
            # Squash merge
            await self.shell.run(["git", "merge", "--squash", source_branch], check=True)
            # Commit
            await self.shell.run(["git", "commit", "-m", message], check=True)
            # Push
            await self.shell.run(["git", "push", "origin", target_branch], check=True)
        except ShellError as e:
            logger.error(f"Failed to squash merge {source_branch} into {target_branch}: {e}")
            _handle_shell_error(e, "Failed to squash merge")

    async def get_commit_log(self, base_branch: str, head_branch: str) -> str:
        """
        Returns the log of commits between base and head.
        """
        try:
            # git log base..head --pretty=format:"%B" (Raw Body)
            result = await self.shell.run(
                ["git", "log", f"{base_branch}..{head_branch}", "--pretty=format:%B"], check=True
            )
            return result.stdout.strip()
        except ShellError as e:
            logger.error(f"Failed to get commit log: {e}")
            _handle_shell_error(e, "Failed to get commit log")

    async def delete_branch(self, branch_name: str) -> None:
        """
        Deletes a branch both locally and remotely.
        Logs warnings if deletion fails but does not raise exceptions.
        """
        try:
            # Delete remote branch
            await self.shell.run(["git", "push", "origin", "--delete", branch_name], check=True)
        except ShellError as e:
            logger.warning(f"Failed to delete remote branch {branch_name}: {e}")

        try:
            # Delete local branch
            await self.shell.run(["git", "branch", "-D", branch_name], check=True)
        except ShellError as e:
            logger.warning(f"Failed to delete local branch {branch_name}: {e}")


class AsyncGitHubInterface:
    """
    Async Interface for interacting with the GitHub CLI (gh).
    """

    def __init__(self, shell_executor: Optional[AsyncShellExecutor] = None) -> None:
        self.executable = "gh"
        self.shell = shell_executor or AsyncShellExecutor()
        if not shutil.which(self.executable):
            logger.warning(f"GitHub CLI executable '{self.executable}' not found in PATH.")

    async def _run_command(self, args: List[str]) -> str:
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
            result = await self.shell.run(command, check=True)
            return result.stdout.strip()
        except ShellError as e:
            logger.error(str(e))
            _handle_shell_error(e, "gh command failed")

    async def get_pr_checks(self) -> List[Dict[str, Any]]:
        """
        Polls GitHub Actions status for the current PR.
        Uses `gh pr checks` to get the status.

        Returns:
            A list containing the checks status.
        """
        logger.info("Polling PR checks...")
        # using --json to get structured data
        output = await self._run_command(["pr", "checks", "--json", "bucket,name,status,conclusion,url"])
        try:
            # We explicitly type the result of json.loads
            parsed: Any = json.loads(output)
            if not isinstance(parsed, list):
                raise ScmError(f"Unexpected format from gh: expected list, got {type(parsed)}")
            # We assume it's a list of dicts based on gh documentation
            return parsed
        except json.JSONDecodeError as e:
            raise ScmError(f"Failed to parse gh output: {output}") from e

    async def get_latest_run_log(self, branch_name: str) -> str:
        """
        Fetches the log of the latest workflow run for the given branch.
        """
        logger.info(f"Fetching latest run logs for branch: {branch_name}")
        try:
            # 1. Get the latest run ID
            output = await self._run_command(
                ["run", "list", "--branch", branch_name, "--limit", "1", "--json", "databaseId"]
            )
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
            log_output = await self._run_command(["run", "view", run_id, "--log"])
            return log_output

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse gh output: {e}")
            return f"Failed to parse run list: {e}"
        except Exception as e:
            logger.error(f"Failed to fetch run logs: {e}")
            return f"Failed to fetch run logs: {e}"


class AsyncGeminiInterface:
    """
    Async Interface for interacting with the Gemini CLI tools.
    """

    def __init__(self, shell_executor: Optional[AsyncShellExecutor] = None, executable: str = "gemini") -> None:
        self.executable = executable
        self.shell = shell_executor or AsyncShellExecutor()
        if not shutil.which(self.executable):
            # We don't raise an error here to allow for testing in environments without gemini
            logger.warning(f"Gemini executable '{self.executable}' not found in PATH.")

    async def _run_command(self, args: List[str]) -> str:
        """
        Executes a gemini command.

        Args:
            args: List of arguments to pass to the gemini command.

        Returns:
            The standard output of the command if successful.

        Raises:
            RuntimeError: If the command fails (non-zero exit code).
        """
        command = [self.executable] + args
        try:
            result = await self.shell.run(command, check=True)
            logger.info("Gemini command successful")
            return result.stdout.strip()
        except ShellError as e:
            logger.error(str(e))
            _handle_shell_error(e, "Gemini command failed")

    async def security_scan(self, path: str = ".") -> str:
        """
        Runs the gemini security scan on the specified path.

        Args:
            path: The path to scan.

        Returns:
            The output of the security scan.
        """
        logger.info(f"Starting security scan on {path}")
        return await self._run_command(["security", "scan", path])

    async def code_review(self, path: str = ".") -> str:
        """
        Runs the gemini code review on the specified path.

        Args:
            path: The path to review.

        Returns:
            The output of the code review.
        """
        logger.info(f"Starting code review on {path}")
        return await self._run_command(["code-review", path])
