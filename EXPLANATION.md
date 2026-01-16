# Refactoring Explanation

The refactoring of `coreason-jules-automator` introduces several architectural improvements to prevent regression bugs and enhance maintainability.

## 1. Type Safety with Pydantic Models
By replacing unstructured `Dict[str, Any]` contexts with Pydantic models (`OrchestrationContext` and `StrategyResult`), we enforce a strict schema for data passing.
- **Prevents KeyErrors:** Missing fields like `branch_name` or `sid` are caught at the boundary (when the model is instantiated) rather than deep inside strategy execution.
- **Validates Types:** Ensures that IDs are strings and other fields match expected types, preventing subtle type-related runtime errors.
- **Immutability:** `OrchestrationContext` is frozen, preventing accidental modification of shared state by strategies, ensuring side-effect-free reads.

## 2. Resource Safety with Async Context Managers
The `AsyncJulesAgent` now implements the Async Context Manager protocol (`__aenter__` and `__aexit__`).
- **Prevents Zombie Processes:** The `__aexit__` method guarantees that the underlying subprocess is terminated (`_cleanup_process`) regardless of whether the operation succeeded, failed, or was cancelled.
- **Simplifies Lifecycle Management:** Consumers like `AsyncOrchestrator` no longer need manual `try...finally` blocks to manage the agent's process, reducing the risk of human error.

## 3. Inversion of Control with Dependency Container
The `Container` class in `di.py` centralizes object construction and dependency wiring.
- **Decoupling:** `cli.py` and `AsyncOrchestrator` are decoupled from the concrete instantiation of their dependencies (like `AsyncGitInterface`, `AsyncJulesAgent`).
- **Testability:** This makes it significantly easier to mock entire subsystems during testing. For example, the orchestration logic can be tested by injecting mock agents and strategies without relying on real shell commands or git operations.

## 4. Domain-Specific Exception Hierarchy
Moving from generic `Exception` or `RuntimeError` to a specific hierarchy (`JulesAutomatorError`, `AgentProcessError`, etc.) allows for more granular error handling.
- **Precise Recovery:** The orchestrator can distinguish between a recoverable agent failure (retryable) and a fatal configuration error (non-retryable).
- **Clearer Debugging:** Tracebacks now carry semantic meaning about the source of the error (e.g., Git operation vs. Agent process crash).
