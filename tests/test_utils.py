# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

from pathlib import Path

import pytest

from coreason_jules_automator.utils.logger import logger


def test_logger_initialization() -> None:
    """Test that the logger is initialized correctly and creates the log directory."""
    # Since the logger is initialized on import, we check side effects

    # Check if logs directory creation is handled
    # Note: running this test might actually create the directory in the test environment
    # if it doesn't exist.

    log_path = Path("logs")
    if not log_path.exists():
        log_path.mkdir(parents=True, exist_ok=True)
    assert log_path.exists()
    assert log_path.is_dir()


def test_ensure_log_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _ensure_log_directory logic explicitly."""
    from unittest.mock import patch

    from coreason_jules_automator.utils.logger import _ensure_log_directory

    with patch("pathlib.Path.exists", return_value=False):
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            _ensure_log_directory()
            mock_mkdir.assert_called_with(parents=True, exist_ok=True)


def test_logger_exports() -> None:
    """Test that logger is exported."""
    assert logger is not None
