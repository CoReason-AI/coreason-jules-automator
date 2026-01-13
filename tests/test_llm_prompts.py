import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from coreason_jules_automator.llm.prompts import PromptManager

def test_prompt_manager_initialization() -> None:
    """Test that PromptManager initializes with default directory."""
    manager = PromptManager()
    assert manager.template_dir.name == "templates"
    assert manager.template_dir.exists()

def test_prompt_manager_custom_directory(tmp_path: Path) -> None:
    """Test initialization with a custom directory."""
    manager = PromptManager(template_dir=tmp_path)
    assert manager.template_dir == tmp_path

def test_prompt_manager_directory_not_exist() -> None:
    """Test initialization with non-existent directory logs warning."""
    non_existent = Path("/non/existent/path")
    # Mock logger to verify warning
    with patch("coreason_jules_automator.llm.prompts.logger") as mock_logger:
        PromptManager(template_dir=non_existent)
        mock_logger.warning.assert_called_once()

def test_render_template(tmp_path: Path) -> None:
    """Test rendering a valid template."""
    template_file = tmp_path / "test.j2"
    template_file.write_text("Hello {{ name }}!")

    manager = PromptManager(template_dir=tmp_path)
    result = manager.render("test.j2", name="Jules")
    assert result == "Hello Jules!"

def test_render_template_not_found() -> None:
    """Test handling of missing templates."""
    manager = PromptManager()
    with pytest.raises(FileNotFoundError):
        manager.render("nonexistent.j2")

def test_render_template_generic_error() -> None:
    """Test handling of generic errors during rendering."""
    manager = PromptManager()
    # Mock env.get_template to raise a generic exception
    manager.env = MagicMock()
    manager.env.get_template.side_effect = Exception("Generic Error")

    with patch("coreason_jules_automator.llm.prompts.logger") as mock_logger:
        with pytest.raises(Exception, match="Generic Error"):
            manager.render("any.j2")
        mock_logger.error.assert_called_with("Error rendering template any.j2: Generic Error")
