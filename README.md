# coreason-jules-automator

coreason-jules-automator

[![CI/CD](https://github.com/CoReason-AI/coreason_jules_automator/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/CoReason-AI/coreason_jules_automator/actions/workflows/ci-cd.yml)
[![Docker](https://github.com/CoReason-AI/coreason_jules_automator/actions/workflows/docker.yml/badge.svg)](https://github.com/CoReason-AI/coreason_jules_automator/actions/workflows/docker.yml)
[![Codecov](https://codecov.io/gh/CoReason-AI/coreason_jules_automator/graph/badge.svg)](https://codecov.io/gh/CoReason-AI/coreason_jules_automator)
[![PyPI](https://img.shields.io/pypi/v/coreason_jules_automator?logo=pypi&logoColor=white)](https://pypi.org/project/coreason_jules_automator/)
[![Python Version](https://img.shields.io/pypi/pyversions/coreason_jules_automator?logo=python&logoColor=white)](https://pypi.org/project/coreason_jules_automator/)
[![License](https://img.shields.io/badge/license-Prosperity--3.0-blue)](https://github.com/CoReason-AI/coreason_jules_automator/blob/main/LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)

The `coreason-jules-automator` is an advanced automation framework designed to streamline development workflows, providing a robust defense pipeline for code quality and security.

## Features

*   **Rich TUI**: A real-time status dashboard provides immediate visibility into the automation process, making it easy to track progress and identify issues as they happen.
*   **Resilience**: Built with declarative retries and exponential backoff, ensuring the system can gracefully handle transient failures and network hiccups without manual intervention.
*   **Type-Safe AI**: Leverages Pydantic for structured LLM outputs, guaranteeing that AI-generated data adheres to strict schemas and reducing runtime errors.

## Core Architecture

The project has evolved from monolithic strategy classes to a modern **Composable Pipeline** architecture.

*   **Pipeline Pattern**: The core logic is broken down into atomic `DefenseStep`s. Each step performs a specific task (e.g., Security Scan, Code Review, Git Push) and can be composed independently.
*   **Atomic Steps**: Steps are self-contained and implement a common interface, making it easy to add, remove, or reorder strategies without affecting the rest of the system.
*   **Dependency Injection**: A robust DI system (`Container`) manages component lifecycles and dependencies, ensuring loose coupling and high testability.

## Getting Started

### Prerequisites

- Python 3.12+
- Poetry

### Installation

1.  Clone the repository:
    ```sh
    git clone https://github.com/CoReason-AI/coreason_jules_automator.git
    cd coreason_jules_automator
    ```
2.  Install dependencies:
    ```sh
    poetry install
    ```

### Usage

-   Run the linter:
    ```sh
    poetry run pre-commit run --all-files
    ```
-   Run the tests:
    ```sh
    poetry run pytest
    ```

### Web Middleware Usage

The library is now natively Asynchronous.

-   Run the example webapp:
    ```bash
    # Run the example FastAPI app
    uvicorn coreason_jules_automator.webapp_example:app --reload
    ```
