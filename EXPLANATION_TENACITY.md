# Tenacity Simplification Explanation

The refactoring to use `tenacity` simplifies the retry logic in the following ways:

1.  **Declarative Configuration**: Instead of manually implementing backoff logic (e.g., `asyncio.sleep`) and attempt counting in a `while` loop, we declare the policy using `wait_exponential` and `stop_after_attempt`. This makes the retry behavior immediately obvious and easier to tune via `Settings`.

2.  **Separation of Concerns**: The control flow for retries is separated from the business logic. The `AsyncRetrying` context manager handles the loop mechanics, allowing the core logic (executing strategies, launching agents) to focus on the task at hand.

3.  **Standardized Retry Triggers**: By raising specific exceptions (like `CycleRetry` or `TryAgain`) to trigger retries, the code becomes more explicit about *why* a retry is happening, rather than relying on conditional breaks or continues within a loop.

4.  **Reduced Boilerplate**: The manual tracking of `attempt` counters and `last_error` variables (mostly) is reduced, and the polling logic in strategies is significantly cleaner without manual `asyncio.sleep` loops.
