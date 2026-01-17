from unittest.mock import MagicMock

from coreason_jules_automator.config import Settings
from coreason_jules_automator.di import PipelineBuilder
from coreason_jules_automator.strategies.steps import CodeReviewStep, SecurityScanStep


def test_pipeline_builder_extensions() -> None:
    settings = MagicMock(spec=Settings)
    # Case 1: No extensions
    settings.extensions_enabled = []

    builder = PipelineBuilder(
        settings=settings,
        gemini=MagicMock(),
        github=MagicMock(),
        git=MagicMock(),
        janitor=MagicMock(),
        llm_client=MagicMock(),
        event_emitter=MagicMock(),
    )

    steps = builder.build()
    # Should have GitPush, CIPolling, LogAnalysis (3 steps)
    assert len(steps) == 3
    assert not any(isinstance(s, SecurityScanStep) for s in steps)
    assert not any(isinstance(s, CodeReviewStep) for s in steps)

    # Case 2: Security only
    settings.extensions_enabled = ["security"]
    steps = builder.build()
    assert len(steps) == 4
    assert any(isinstance(s, SecurityScanStep) for s in steps)
    assert not any(isinstance(s, CodeReviewStep) for s in steps)

    # Case 3: Both
    settings.extensions_enabled = ["security", "code-review"]
    steps = builder.build()
    assert len(steps) == 5
    assert any(isinstance(s, SecurityScanStep) for s in steps)
    assert any(isinstance(s, CodeReviewStep) for s in steps)
