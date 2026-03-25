from __future__ import annotations

from datetime import datetime


STREAM_MODES = ["messages", "updates"]


def log_section(title: str) -> None:
    print(f"\n{'=' * 20} {title} {'=' * 20}")


def log_step(agent_name: str, message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {agent_name}: {message}")


def log_tool_call(
    agent_name: str, tool_name: str, arguments: dict | None = None
) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] {agent_name} -> TOOL CALL: {tool_name}")
    if arguments:
        print(arguments)


def log_tool_result(tool_name: str, result: object) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] TOOL RESULT: {tool_name}")
    print(result)


def handle_stream(agent_name: str, content: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] {agent_name}")
    print(content)
