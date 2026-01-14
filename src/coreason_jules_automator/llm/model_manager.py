from pathlib import Path

from huggingface_hub import hf_hub_download

from coreason_jules_automator.utils.logger import logger


class ModelManager:
    """Manages local LLM models."""

    def ensure_model_downloaded(self) -> str:
        """
        Ensures the local GGUF model is downloaded to ~/.cache/coreason/.
        Returns the path to the model file.
        """
        repo_id = "TheBloke/DeepSeek-Coder-1.3B-Instruct-GGUF"
        filename = "deepseek-coder-1.3b-instruct.Q4_K_M.gguf"
        cache_dir = Path.home() / ".cache" / "coreason"

        logger.info(f"Ensuring model {repo_id}/{filename} is present in {cache_dir}")
        try:
            model_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                cache_dir=str(cache_dir),
                local_dir=str(cache_dir),  # Force download to specific dir for simplicity
                local_dir_use_symlinks=False,  # type: ignore[call-overload, unused-ignore]
            )
            # Explicitly cast to str for mypy, as hf_hub_download returns str | None in some versions or Any
            return str(model_path)
        except Exception as e:
            raise RuntimeError(f"Failed to download model: {e}") from e
