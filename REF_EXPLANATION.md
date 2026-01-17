# How to Add a New "Linting" Step

This guide explains how to add a new step to the defense pipeline without modifying existing core logic, adhering to the Open-Closed Principle.

## 1. Create the Step Class
Create a new class in a new file (e.g., `src/coreason_jules_automator/strategies/linting.py`) or add to `src/coreason_jules_automator/strategies/steps.py`.
It must satisfy the `DefenseStep` protocol.

```python
from coreason_jules_automator.domain.pipeline import DefenseStep
from coreason_jules_automator.domain.context import OrchestrationContext, StrategyResult
from coreason_jules_automator.async_api.scm import AsyncGeminiInterface # or other dependencies

class LintingStep:
    def __init__(self, gemini: AsyncGeminiInterface):
        self.gemini = gemini

    async def execute(self, context: OrchestrationContext) -> StrategyResult:
        # Perform linting logic here
        # e.g., result = await self.gemini.run_linter()

        # Determine success
        passed = True # ...

        if passed:
            return StrategyResult(success=True, message="Linting passed")
        else:
            return StrategyResult(success=False, message="Linting failed")
```

## 2. Register in PipelineBuilder
Modify `src/coreason_jules_automator/di.py` to include the new step in the `PipelineBuilder.build` method.

```python
    def build(self) -> List[DefenseStep]:
        steps: List[DefenseStep] = []

        # ... existing steps ...

        # Add Linting Step
        if "linting" in self.settings.extensions_enabled:
             # Assuming you injected necessary dependencies into PipelineBuilder
             steps.append(LintingStep(gemini=self.gemini))

        # ... other steps ...

        return steps
```

## 3. Update Dependencies (if needed)
If `LintingStep` requires new dependencies, add them to `Container.__init__` and pass them to `PipelineBuilder`.
