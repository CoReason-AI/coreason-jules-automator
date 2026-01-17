import sys
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from coreason_jules_automator.config import Settings
from coreason_jules_automator.di import Container, PipelineBuilder
from coreason_jules_automator.strategies.steps import (
    CIPollingStep,
    CodeReviewStep,
    GitPushStep,
    LogAnalysisStep,
    SecurityScanStep,
)


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock(spec=Settings)
    settings.extensions_enabled = ["security", "code-review"]
    settings.llm_strategy = "api"
    settings.DEEPSEEK_API_KEY = None
    settings.OPENAI_API_KEY = None
    return settings


# --- PipelineBuilder Tests ---


def test_pipeline_builder_full(mock_settings: MagicMock) -> None:
    builder = PipelineBuilder(
        settings=mock_settings,
        gemini=MagicMock(),
        github=MagicMock(),
        git=MagicMock(),
        janitor=MagicMock(),
        llm_client=MagicMock(),
        event_emitter=MagicMock(),
    )
    steps = builder.build()
    assert len(steps) == 5
    assert isinstance(steps[0], SecurityScanStep)
    assert isinstance(steps[1], CodeReviewStep)
    assert isinstance(steps[2], GitPushStep)
    assert isinstance(steps[3], CIPollingStep)
    assert isinstance(steps[4], LogAnalysisStep)


def test_pipeline_builder_minimal(mock_settings: MagicMock) -> None:
    mock_settings.extensions_enabled = []
    builder = PipelineBuilder(
        settings=mock_settings,
        gemini=MagicMock(),
        github=MagicMock(),
        git=MagicMock(),
        janitor=MagicMock(),
        llm_client=MagicMock(),
        event_emitter=MagicMock(),
    )
    steps = builder.build()
    assert len(steps) == 3
    # Security and CodeReview skipped
    assert isinstance(steps[0], GitPushStep)
    assert isinstance(steps[1], CIPollingStep)
    assert isinstance(steps[2], LogAnalysisStep)


# --- Container Tests ---


@patch("coreason_jules_automator.di.get_settings")
@patch("coreason_jules_automator.di.AsyncGitHubInterface")
@patch("coreason_jules_automator.di.AsyncGitInterface")
@patch("coreason_jules_automator.di.AsyncGeminiInterface")
@patch("coreason_jules_automator.di.AsyncShellExecutor")
def test_container_init_deepseek(
    mock_shell: MagicMock,
    mock_gemini: MagicMock,
    mock_git: MagicMock,
    mock_github: MagicMock,
    mock_get_settings: MagicMock,
) -> None:
    settings = MagicMock(spec=Settings)
    settings.llm_strategy = "api"
    settings.DEEPSEEK_API_KEY = SecretStr("ds-key")
    settings.OPENAI_API_KEY = None
    settings.extensions_enabled = []
    mock_get_settings.return_value = settings

    with patch("openai.AsyncOpenAI") as mock_openai:
        container = Container()
        assert container.llm_client is not None
        mock_openai.assert_called_with(api_key="ds-key", base_url="https://api.deepseek.com")


@patch("coreason_jules_automator.di.get_settings")
@patch("coreason_jules_automator.di.AsyncGitHubInterface")
@patch("coreason_jules_automator.di.AsyncGitInterface")
@patch("coreason_jules_automator.di.AsyncGeminiInterface")
@patch("coreason_jules_automator.di.AsyncShellExecutor")
def test_container_init_openai(
    mock_shell: MagicMock,
    mock_gemini: MagicMock,
    mock_git: MagicMock,
    mock_github: MagicMock,
    mock_get_settings: MagicMock,
) -> None:
    settings = MagicMock(spec=Settings)
    settings.llm_strategy = "api"
    settings.DEEPSEEK_API_KEY = None
    settings.OPENAI_API_KEY = SecretStr("oa-key")
    settings.extensions_enabled = []
    mock_get_settings.return_value = settings

    with patch("openai.AsyncOpenAI") as mock_openai:
        container = Container()
        assert container.llm_client is not None
        mock_openai.assert_called_with(api_key="oa-key")


@patch("coreason_jules_automator.di.get_settings")
@patch("coreason_jules_automator.di.AsyncGitHubInterface")
@patch("coreason_jules_automator.di.AsyncGitInterface")
@patch("coreason_jules_automator.di.AsyncGeminiInterface")
@patch("coreason_jules_automator.di.AsyncShellExecutor")
def test_container_init_no_keys(
    mock_shell: MagicMock,
    mock_gemini: MagicMock,
    mock_git: MagicMock,
    mock_github: MagicMock,
    mock_get_settings: MagicMock,
) -> None:
    settings = MagicMock(spec=Settings)
    settings.llm_strategy = "api"
    settings.DEEPSEEK_API_KEY = None
    settings.OPENAI_API_KEY = None
    settings.extensions_enabled = []
    mock_get_settings.return_value = settings

    container = Container()
    assert container.llm_client is None


@patch("coreason_jules_automator.di.get_settings")
@patch("coreason_jules_automator.di.AsyncGitHubInterface")
@patch("coreason_jules_automator.di.AsyncGitInterface")
@patch("coreason_jules_automator.di.AsyncGeminiInterface")
@patch("coreason_jules_automator.di.AsyncShellExecutor")
def test_container_init_openai_import_error(
    mock_shell: MagicMock,
    mock_gemini: MagicMock,
    mock_git: MagicMock,
    mock_github: MagicMock,
    mock_get_settings: MagicMock,
) -> None:
    settings = MagicMock(spec=Settings)
    settings.llm_strategy = "api"
    settings.extensions_enabled = []
    mock_get_settings.return_value = settings

    with patch.dict(sys.modules, {"openai": None}):
        container = Container()
        assert container.llm_client is None


@patch("coreason_jules_automator.di.get_settings")
@patch("coreason_jules_automator.di.AsyncGitHubInterface")
@patch("coreason_jules_automator.di.AsyncGitInterface")
@patch("coreason_jules_automator.di.AsyncGeminiInterface")
@patch("coreason_jules_automator.di.AsyncShellExecutor")
def test_container_init_local_strategy(
    mock_shell: MagicMock,
    mock_gemini: MagicMock,
    mock_git: MagicMock,
    mock_github: MagicMock,
    mock_get_settings: MagicMock,
) -> None:
    settings = MagicMock(spec=Settings)
    settings.llm_strategy = "local"
    settings.extensions_enabled = []
    mock_get_settings.return_value = settings

    container = Container()
    assert container.llm_client is None
