# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_jules_automator

from coreason_jules_automator.protocols.jules import (
    Action,
    JulesProtocol,
    SendStdin,
    SignalComplete,
    SignalSessionId,
)


def test_protocol_initialization() -> None:
    protocol = JulesProtocol()
    assert protocol._buffer == ""


def test_process_output_no_match() -> None:
    protocol = JulesProtocol()
    actions = list(protocol.process_output("Some random output\n"))
    assert len(actions) == 0
    assert protocol._buffer == "Some random output\n"


def test_process_output_prompt_question_mark() -> None:
    protocol = JulesProtocol()
    actions = list(protocol.process_output("Do you want to continue?"))
    assert len(actions) == 1
    assert isinstance(actions[0], SendStdin)
    assert actions[0].text == "Use your best judgment and make autonomous decisions.\n"
    assert protocol._buffer == ""


def test_process_output_prompt_yn() -> None:
    protocol = JulesProtocol()
    actions = list(protocol.process_output("Continue [y/n]"))
    assert len(actions) == 1
    assert isinstance(actions[0], SendStdin)
    assert protocol._buffer == ""


def test_process_output_success() -> None:
    protocol = JulesProtocol()
    actions = list(protocol.process_output("Task finished. 100% of the requirements is met."))
    assert len(actions) == 1
    assert isinstance(actions[0], SignalComplete)
    # The period after "is met" is NOT consumed
    assert protocol._buffer == "."


def test_process_output_partial_match() -> None:
    protocol = JulesProtocol()
    actions = list(protocol.process_output("100% of the requirements "))
    assert len(actions) == 0
    actions = list(protocol.process_output("is met"))
    assert len(actions) == 1
    assert isinstance(actions[0], SignalComplete)
    assert protocol._buffer == ""


def test_process_output_multiple_matches() -> None:
    protocol = JulesProtocol()
    # "Question? Answer. 100% of the requirements is met."
    actions = list(protocol.process_output("Question? Answer. 100% of the requirements is met."))
    assert len(actions) == 2
    assert isinstance(actions[0], SendStdin)
    assert isinstance(actions[1], SignalComplete)


def test_process_output_mixed_order() -> None:
    protocol = JulesProtocol()
    actions = list(protocol.process_output("100% of the requirements is met. Continue?"))
    assert len(actions) == 2
    assert isinstance(actions[0], SignalComplete)
    assert isinstance(actions[1], SendStdin)


def test_action_classes() -> None:
    # Cover the dataclasses
    a = SendStdin("text")
    assert a.text == "text"
    b = SignalSessionId("123")
    assert b.sid == "123"
    c = SignalComplete()
    assert isinstance(c, Action)


def test_process_output_sid() -> None:
    protocol = JulesProtocol()
    actions = list(protocol.process_output("Starting... Session ID: 12345"))
    assert len(actions) == 1
    assert isinstance(actions[0], SignalSessionId)
    assert actions[0].sid == "12345"
    assert protocol._buffer == ""
