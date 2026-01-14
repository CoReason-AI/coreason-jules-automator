# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

import re
from dataclasses import dataclass
from typing import Iterator


@dataclass
class Action:
    pass


@dataclass
class SendStdin(Action):
    text: str


@dataclass
class SignalSessionId(Action):
    sid: str


@dataclass
class SignalComplete(Action):
    pass


class JulesProtocol:
    """
    Sans-I/O Protocol for the Jules agent interaction.
    Parses output chunks and yields actions.
    """

    def __init__(self) -> None:
        self._buffer = ""
        # 0: Question
        self._prompt_pattern = re.compile(r"\?|\[y/n\]")
        # 1: Success Signal
        self._success_pattern = re.compile(r"100% of the requirements is met", re.IGNORECASE)
        # 2: Session ID
        self._sid_pattern = re.compile(r"Session ID: (\S+)")

    def process_output(self, chunk: str) -> Iterator[Action]:
        """
        Feeds a chunk of stdout/stderr to the protocol.
        Yields actions if patterns are matched.
        """
        self._buffer += chunk

        while True:
            match_prompt = self._prompt_pattern.search(self._buffer)
            match_success = self._success_pattern.search(self._buffer)
            match_sid = self._sid_pattern.search(self._buffer)

            # Find the earliest match
            matches = []
            if match_prompt:
                matches.append((match_prompt.start(), "prompt", match_prompt))
            if match_success:
                matches.append((match_success.start(), "success", match_success))
            if match_sid:
                matches.append((match_sid.start(), "sid", match_sid))

            if not matches:
                break

            # Sort by start index to handle order of appearance
            matches.sort(key=lambda x: x[0])
            start_idx, match_type, match_obj = matches[0]

            # Consume buffer up to the end of the match
            end_idx = match_obj.end()

            # Note: We consume up to the match.
            # Any text before the match is discarded/ignored as noise
            # or could be logged by the caller before passing to process_output.
            self._buffer = self._buffer[end_idx:]

            if match_type == "prompt":
                # Auto-reply
                yield SendStdin("Use your best judgment and make autonomous decisions.\n")
            elif match_type == "success":
                yield SignalComplete()
            elif match_type == "sid":
                sid = match_obj.group(1)
                yield SignalSessionId(sid)
