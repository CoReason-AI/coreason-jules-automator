from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from coreason_jules_automator.utils.logger import logger


class PromptManager:
    """
    Manages loading and rendering of Jinja2 templates for LLM prompts.
    """

    def __init__(self, template_dir: Optional[Path] = None) -> None:
        if template_dir is None:
            # Default to the templates directory inside the package
            # This file is in src/coreason_jules_automator/llm/prompts.py
            # We want src/coreason_jules_automator/templates
            template_dir = Path(__file__).parent.parent / "templates"

        self.template_dir = template_dir

        if not self.template_dir.exists():
            logger.warning(f"Template directory does not exist: {self.template_dir}")

        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, **kwargs: Any) -> str:
        """
        Renders a template with the provided context.
        """
        try:
            template = self.env.get_template(template_name)
            # jinja2 render returns str in recent versions, but mypy might see Any depending on stubs
            return str(template.render(**kwargs))
        except TemplateNotFound:
            logger.error(f"Template not found: {template_name} in {self.template_dir}")
            raise FileNotFoundError(f"Template not found: {template_name}") from None
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            raise
