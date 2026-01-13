from typing import Optional

from coreason_jules_automator.utils.logger import logger
from coreason_jules_automator.utils.shell import ShellError, ShellExecutor


class GitInterface:
    """
    Interface for interacting with the git CLI.
    """

    def __init__(self, shell_executor: Optional[ShellExecutor] = None) -> None:
        self.shell = shell_executor or ShellExecutor()

    async def push_to_branch(self, branch_name: str, message: str) -> None:
        """
        Pushes changes to a specific branch.

        Args:
            branch_name: The name of the branch to push to.
            message: The commit message.

        Raises:
            RuntimeError: If any git command fails.
        """
        logger.info(f"Pushing to branch {branch_name}")
        try:
            await self.shell.run_async(["git", "add", "."], check=True)
            await self.shell.run_async(["git", "commit", "-m", message], check=True)
            await self.shell.run_async(["git", "push", "origin", branch_name], check=True)
        except ShellError as e:
            logger.error(f"Git push failed: {e}")
            raise RuntimeError(f"Git push failed: {e}") from e
