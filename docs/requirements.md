# Software Requirements & Vision: The "Coreason Jules Automator"

## Introduction

This document outlines the vision and technical requirements for the **"Coreason Jules Automator"**, an autonomous orchestration engine designed to optimize software development workflows by integrating fast local feedback loops with robust remote CI/CD verification.

## Vision

The goal is to empower developers with an autonomous agent (**Jules**) that operates within a strict "Clean Room" environment. This environment utilizes a **"Two-Line Defense"** architecture to ensure high-quality, secure, and tested code delivery without sacrificing velocity.

## Core Architecture: The "Two-Line" Defense

The system is built around a nested feedback loop managed by a central State Machine. This design balances the need for speed ("The Bloat") with the need for absolute correctness ("The Truth").

### Line 1: Fast/Local ("The Bloat")

*   **Goal:** Optimize for speed and save CI minutes by catching issues locally.
*   **Trigger:** Executed immediately after the Agent generates code.
*   **Actions:**
    *   **Security Scan:** Runs `gemini security` to identify potential vulnerabilities.
    *   **Code Review:** Runs `gemini code-review` to ensure code quality and adherence to standards.
*   **Outcome:**
    *   **Failure:** Specific errors are fed back to the Agent immediately. Code is **NOT** pushed to GitHub.
    *   **Success:** Proceed to Line 2.

### Line 2: Slow/Remote ("The Truth")

*   **Goal:** Authoritative verification via GitHub CI/CD.
*   **Trigger:** Activated only after Line 1 passes.
*   **Actions:**
    *   **Push:** Code is pushed to a task branch.
    *   **Verify:** Polls GitHub Actions (`gh pr checks`) to verify the build.
*   **Workflow:** Implements the **Red-Green-Refactor** TDD loop:
    1.  **Red:** Verify that a new test case fails (Reproduction).
    2.  **Green:** Verify that the fix passes.
    3.  **Refactor:** If CI fails (linting/tests), the **"Janitor" LLM** analyzes the logs and provides summarized feedback to the Agent.

## Component Specifications & User Requirements

### 1. Configuration Settings

The application is configured via environment variables with a `COREASON_` prefix, ensuring security and flexibility.

*   **Tunable Settings:**
    *   `llm_strategy`: Choose between `"api"` (default, for speed) and `"local"` (fallback).
    *   `extensions_enabled`: Select active extensions (e.g., `["security", "code-review"]`).
    *   `max_retries`: Set the maximum number of retry attempts (default: 5).

*   **Security & Authentication:**
    *   **GITHUB_TOKEN:** Critical for CI/CD operations. Validated on startup but never logged.
    *   **GOOGLE_API_KEY:** Required for Jules and Gemini CLI extensions.
    *   **Optional Keys:** `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` (for API mode), `SSH_PRIVATE_KEY` (for git operations).

### 2. The Hybrid "Janitor" LLM

An intelligent abstraction layer that manages LLM interactions and maintenance tasks.

*   **Modes:**
    *   **API Mode:** Utilizes OpenAI or DeepSeek clients for high-performance inference.
    *   **Local Mode:** Falls back to `llama-cpp-python` if API keys are missing or connectivity is lost. It automatically downloads necessary quantization models (e.g., DeepSeek-Coder) to the local cache.
*   **Capabilities:**
    *   **Commit Sanitization:** Removes metadata like "Co-authored-by" and bot signatures from commit messages.
    *   **Log Summarization:** Condenses lengthy CI failure logs (e.g., 1000 lines) into concise, actionable hints (e.g., 3 sentences).

### 3. The Agent Interface

A robust wrapper around the `jules` agent to facilitate seamless interaction and control.

*   **Context Injection:** Automatically injects project specifications (e.g., from `SPEC.md`) into the Agent's prompt to ensure context-aware generation.
*   **Autonomous Decision Making:** Handles routine queries (e.g., "Should I...") with auto-replies ("Use your best judgment") to maintain momentum.

### 4. Orchestrator (The Brain)

The central nervous system that connects Line 1 and Line 2 logic. It manages the state transitions:
1.  Agent submits code.
2.  **Line 1:** Local checks run. If fail -> Retry.
3.  **Line 2:** Remote CI runs. If fail -> "Janitor" analyzes -> Retry.
4.  **Success:** Task completed.

## User Interface

The system provides a **Command Line Interface (CLI)** built with `typer`.
*   Designed to run as a background service (e.g., using `nohup`).
*   Provides clear, real-time feedback on the orchestration process.

---
*This document reflects the "Coreason Jules Automator" implementation plan and architectural vision.*
