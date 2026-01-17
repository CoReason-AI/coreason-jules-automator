# Architecture

The `coreason-jules-automator` utilizes a modern, modular architecture centered around Dependency Injection (DI) and a Composable Pipeline. This design promotes testability, flexibility, and ease of extension.

## Dependency Injection (DI)

The core wiring of the application is handled by the `Container` class located in `src/coreason_jules_automator/di.py`.

The `Container` is responsible for:
*   **Loading Configuration**: Reading settings from environment variables and `.env` files.
*   **Initializing Core Components**: Setting up logging, event collection, and shell executors.
*   **Instantiating Services**: creating instances of LLM clients, SCM interfaces (GitHub, Git, Gemini), and helper services like `JanitorService`.
*   **Building the Pipeline**: using `PipelineBuilder` to construct the list of defense steps based on enabled extensions.
*   **Wiring the Orchestrator**: Injecting all necessary dependencies into the `AsyncOrchestrator` and `AsyncJulesAgent`.

This centralized configuration allows for easy swapping of implementations (e.g., using a mock LLM client for testing) and ensures that components remain loosely coupled.

## Composable Pipeline

The defense strategy is implemented as a pipeline of atomic steps. Each step implements the `DefenseStep` protocol (conceptually, though currently defined as a class with an `execute` method).

### Defense Steps

A `DefenseStep` is a self-contained unit of logic that performs a specific check or action. Examples include:
*   `SecurityScanStep`: Runs security scans using Gemini.
*   `CodeReviewStep`: Performs AI-based code review.
*   `GitPushStep`: Pushes changes to the remote repository.
*   `CIPollingStep`: Monitors CI/CD status.
*   `LogAnalysisStep`: Analyzes logs upon CI failure.

### Extending the System

To add a new defense step:

1.  **Create the Step Class**: Define a new class in `src/coreason_jules_automator/strategies/steps.py` (or a new file). It must implement an `async def execute(self, context: OrchestrationContext) -> StrategyResult` method.

    ```python
    from coreason_jules_automator.domain.context import OrchestrationContext, StrategyResult

    class MyNewStep:
        def __init__(self, dependency):
            self.dependency = dependency

        async def execute(self, context: OrchestrationContext) -> StrategyResult:
            # Your logic here
            return StrategyResult(success=True, message="My step passed")
    ```

2.  **Register the Step**: Update `src/coreason_jules_automator/di.py` within the `PipelineBuilder.build` method to include your new step in the returned list.

    ```python
    # src/coreason_jules_automator/di.py

    def build(self) -> List[DefenseStep]:
        steps = []
        # ... existing steps ...
        steps.append(MyNewStep(self.some_dependency))
        return steps
    ```

This architecture allows developers to easily plug in new checks or modify the order of execution without rewriting the core orchestration logic.
