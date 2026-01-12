# **AGENTS.md**

**Note to Agent:** This file contains strict rules and context for this repository. Read this before planning or executing tasks.

# **PRIMARY DIRECTIVE: STRICT DEVELOPMENT PROTOCOL**

**You are an advanced coding LLM tasked with implementing changes in this repository. It is imperative that you adhere strictly to this iterative, atomic, and test-driven development protocol. Do not attempt to implement the entire specification at once.**

## **The Protocol:**

1. **Comprehensive Analysis:** Thoroughly review the user's request and the detailed specifications provided. Examine the current state of the existing codebase to understand the existing architecture and what has already been implemented.
2. **Decomposition and Planning:** Identify the delta between the current codebase and the specification. Break down all pending work into a list of small, atomic units. An atomic unit must be independently implementable and testable. **You MUST print all pending work as atomic units prior to selecting the first task.**
3. **Select ONE Atomic Unit (The "One Step" Rule):** Choose one and only one atomic unit from your list to implement in this iteration. Select the smallest possible increment that moves the project toward the goal.
4. **Implementation:** Build the functionality for this single atomic unit, ensuring it adheres strictly to the architectural patterns defined in this document.
5. **Rigorous Testing:** Write comprehensive unit tests specifically for the implemented unit. This must include positive tests, negative tests, boundary conditions, and all foreseeable edge cases.
6. **Validation and Regression Check:** Ensure all newly added tests pass. Crucially, verify that all pre-existing tests still pass. There must be zero regressions.
   * *Constraint:* If a test fails more than twice after attempted fixes, STOP and re-evaluate the implementation strategy. Do not loop endlessly.
7. **Commit:** Deliver the complete, high-quality implementation and its corresponding tests, ready for an atomic commit.

## **1. Project Overview**

* **Name:** coreason-jules-automator (The "Vibe Runner")
* **Type:** Python Application / Library
* **Language:** Python 3.12, 3.13, 3.14 (Latest 3 versions)
* **Package Manager:** Poetry
* **License:** Prosperity Public License 3.0 (Proprietary/Dual-licensed)
* **Project Structure:** src layout (source code resides in src/coreason_jules_automator)

## **2. Environment & Commands**

The project is managed via Poetry. Do not use pip directly unless inside a Docker build stage.

* **Install Dependencies:** `poetry install`
* **Run Linter (Pre-commit):** `poetry run pre-commit run --all-files`
* **Run Tests:** `poetry run pytest`
* **Run Application:** `poetry run vibe-runner`
* **Build Package:** `poetry build` (or `python -m build` in CI)

## **3. Development Rules**

### **Code Style & Quality**

This project uses **Ruff** for Python linting/formatting, **Mypy** for typing, and **Hadolint** for Dockerfiles.

* **Formatting:** Do not manually format. Run `poetry run ruff format .`
* **Linting:** Fix violations automatically where possible: `poetry run ruff check --fix .`
* **Docker Linting:** Checked via pre-commit (hadolint).
* **Typing:**
  * Strict static typing is encouraged.
  * Run checks with: `poetry run mypy .`
  * Avoid `Any` wherever possible.
* **Logging:** Use the project's centralized logging configuration.
  * *Good:* `from src.coreason_jules_automator.utils.logger import logger -> logger.info("...")`
* **Licensing:** Every .py file must start with the standard license header.

### **Legal & Intellectual Property**

**Strict Prohibition on External Code:**
You are strictly forbidden from copying, reproducing, imitating, or drawing from any external codebases, especially GPL, AGPL, or other non-permissive/copyleft licenses. All generated logic must be original or derived from permissively licensed (e.g., MIT, Apache 2.0) sources and properly attributed.

### **File Structure**

* **Source Code:** `src/coreason_jules_automator/`
  * `cli.py`: Entry point (Typer/Click).
  * `config.py`: Pydantic settings.
  * `orchestrator.py`: Main State Machine.
  * `agent/`: Interfaces for external agents (Jules).
  * `ci/`: Interfaces for GitHub/CI.
  * `llm/`: Local and API Hybrid providers.
  * `interfaces/`: Wrappers for "Borrowed" tools (Gemini extensions).
* **Tests:** `tests/`
  * Test files must start with `test_`.

### **Testing Guidelines**

**Mandatory Requirement: 100% Test Coverage.**

* **Strategy:**
  * **Mocking is Mandatory for Agents/LLMs:** You **MUST** mock `pexpect` sessions, `llama_cpp.Llama` objects, and API calls during standard unit tests. **Never load a 4GB GGUF model during a test run.**
  * **State Machine Verification:** Tests must verify the logic of the "Red-Green-Refactor" transitions (e.g., verify that a CI failure triggers the Remediation Loop).
* **Safety:** Never hardcode credentials in tests. Use environment variables.

## **4. Vibe Runner Architecture (Specific Mandates)**

This project implements a **Hybrid "Two-Line" Defense** architecture.

### **A. The "Borrowed" Tools (Line 1 - Fast/Local)**
We leverage existing Gemini CLI Extensions as the first line of defense. The Orchestrator must enforce their presence:
* **Jules:** The Worker Agent (Required).
* **Conductor:** Context Provider (Optional/Supported).
* **Security:** Vulnerability Scanner (Required).
* **Code Review:** Linter/Style Checker (Required).

### **B. The Orchestrator (Line 2 - Slow/Authoritative)**
The Python logic (`orchestrator.py`) acts as the "Supervisor". It strictly enforces the **Red-Green-Refactor** TDD loop:
1.  **Red:** Command Jules to reproduce the bug/feature with a failing test.
2.  **Green:** Command Jules to implement the fix.
3.  **Refactor/Verify:** Push to GitHub and poll CI/CD.

### **C. The "Janitor" LLM Strategy**
We employ a **Hybrid LLM Strategy** for sanitization and summarization:
* **Primary:** API-based (DeepSeek/OpenAI) for speed and quality (if keys present).
* **Fallback:** Local embedded LLM (`llama-cpp-python` with `DeepSeek-Coder-1.3B-Instruct-GGUF`) for offline capability.
* **Tasks:** Rewriting commit messages (removing "Co-authored-by") and summarizing CI logs.

## **5. Configuration Standards**

Adhere to 12-Factor App principles. Use `pydantic-settings` with the `VIBE_` prefix.

* **Core:**
  * `VIBE_RUN_ID`: Unique run identifier.
  * `VIBE_MAX_RETRIES`: Max loops for CI fixes (Default: 5).
  * `VIBE_REPO_PATH`: Path to target repo.
* **Strategies:**
  * `VIBE_LLM_STRATEGY`: `local` or `api`.
  * `VIBE_EXTENSIONS_ENABLED`: List of required Gemini extensions.
* **Secrets:**
  * `OPENAI_API_KEY` / `DEEPSEEK_API_KEY`: For API strategy.
  * `SSH_PRIVATE_KEY`: For remote operations.

## **6. Docker & Deployment**

* **Multi-stage Build:** The Dockerfile has a builder stage and a runtime stage.
* **User:** The app runs as a non-root user (`appuser`).
* **Base Image:** `python:3.12-slim` (Must support compiling `llama-cpp-python`).

## **7. Workflow & Debugging Protocol**

If you encounter an error (e.g., test failure, linting error), follow this STRICT sequence:

1. **Read the Logs:** Do not guess. Read the complete error message.
2. **Isolate:** If multiple tests fail, focus on the simplest failure first.
3. **Reproduction:** If the error is obscure, create a minimal reproduction case within the test suite.
4. **Fix:** Apply the fix.
5. **Verify:** Run the specific test case again.

## **8. Human-in-the-Loop Triggers**

STOP and ASK the user before:

* Modifying database migrations or schema files.
* Deleting any file outside of `src/` or `tests/`.
* Adding a dependency that requires OS-level libraries (beyond those needed for `llama-cpp-python` build).
* Committing any secrets.