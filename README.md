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

## Getting Started

### Prerequisites

- Python 3.12+
- Poetry

### Installation

1.  Clone the repository:
    ```sh
    git clone https://github.com/example/example.git
    cd my_python_project
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
