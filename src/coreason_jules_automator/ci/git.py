from typing import Optional

from coreason_jules_automator.utils.logger import logger
from coreason_jules_automator.utils.shell import ShellError, ShellExecutor


class GitInterface:
    """
    Interface for interacting with the git CLI.
    """

    def __init__(self, shell_executor: Optional[ShellExecutor] = None) -> None:
        self.shell = shell_executor or ShellExecutor()

    def has_changes(self) -> bool:
        """
        Checks if there are any changes in the git repository.

        Returns:
            True if there are changes, False otherwise.
        """
        try:
            result = self.shell.run(["git", "status", "--porcelain"], check=True)
            return bool(result.stdout.strip())
        except ShellError as e:
            logger.error(f"Git status check failed: {e}")
            return False

    def push_to_branch(self, branch_name: str, message: str) -> bool:
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
            self.shell.run(["rm", "-f", ".git/index.lock"], check=False)

            # 2. Add changes
            self.shell.run(["git", "add", "."], check=True)

            # 3. Check for changes
            if not self.has_changes():
                logger.warning("⚠️ No changes detected. Skipping commit and push.")
                return False

            # 4. Commit and Push
            self.shell.run(["git", "commit", "-m", message], check=True)
            self.shell.run(["git", "push", "origin", branch_name], check=True)
            return True

        except ShellError as e:
            logger.error(f"Git push failed: {e}")
            raise RuntimeError(f"Git push failed: {e}") from e

    def checkout_new_branch(self, branch_name: str, base_branch: str) -> None:
        """
        Creates and checks out a new branch from a base branch.
        """
        try:
            # Check out base first to ensure we are clean/up-to-date
            self.shell.run(["git", "checkout", base_branch], check=True)
            self.shell.run(["git", "pull", "origin", base_branch], check=True)
            # Create new branch
            self.shell.run(["git", "checkout", "-b", branch_name], check=True)
        except ShellError as e:
            logger.error(f"Failed to checkout new branch {branch_name} from {base_branch}: {e}")
            raise RuntimeError(f"Failed to checkout new branch: {e}") from e

    def merge_squash(self, source_branch: str, target_branch: str, message: str) -> None:
        """
        Squash merges source_branch into target_branch with a custom message.
        """
        try:
            self.shell.run(["git", "checkout", target_branch], check=True)
            # Squash merge
            self.shell.run(["git", "merge", "--squash", source_branch], check=True)
            # Commit
            self.shell.run(["git", "commit", "-m", message], check=True)
        except ShellError as e:
            logger.error(f"Failed to squash merge {source_branch} into {target_branch}: {e}")
            raise RuntimeError(f"Failed to squash merge: {e}") from e

    def get_commit_log(self, base_branch: str, head_branch: str) -> str:
        """
        Returns the log of commits between base and head.
        """
        try:
            # git log base..head --pretty=format:"%s"
            result = self.shell.run(["git", "log", f"{base_branch}..{head_branch}", "--pretty=format:%s"], check=True)
            return result.stdout.strip()
        except ShellError as e:
            logger.error(f"Failed to get commit log: {e}")
            raise RuntimeError(f"Failed to get commit log: {e}") from e
