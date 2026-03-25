"""
Utilities for streaming agent or LLM output with rich terminal logging.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from datetime import datetime
from typing import Any, AsyncIterator, Iterator, Optional, Sequence, Union

from langchain.messages import AIMessage, AIMessageChunk, ToolMessage
from langgraph.types import StreamMode


STREAM_MODES: Sequence[StreamMode] = ["messages", "updates"]


class _C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _divider(label: str, color: str = _C.BLUE) -> None:
    ts = _ts()
    label = f"{_C.BOLD}{ts} {label}{_C.RESET}"
    line = "\u2500" * 60
    print(f"\n{color}{_C.BOLD}{line}{_C.RESET}")
    print(f"{color}{_C.BOLD}  {label}{_C.RESET}")
    print(f"{color}{_C.BOLD}{line}{_C.RESET}")


def log_section(title: str) -> None:
    _divider(title, _C.BLUE)


def _log_simple(detail: str = "", color: str = _C.GRAY) -> None:
    print(f"{color}{detail}{_C.RESET}")


class _LoadingSpinner:
    def __init__(self, message: str):
        self.message = message
        self.running = False
        self.thread = None
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.frame_idx = 0

    def _animate(self) -> None:
        while self.running:
            frame = self.frames[self.frame_idx % len(self.frames)]
            sys.stdout.write(f"\r{_C.RED}{frame} {self.message}{_C.RESET}")
            sys.stdout.flush()
            self.frame_idx += 1
            time.sleep(0.1)

    def start(self) -> None:
        self.running = True
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join(timeout=0.5)
            sys.stdout.write("\r" + " " * (len(self.message) + 5) + "\r")
            sys.stdout.flush()


def log_input(content: str, agent_name: str = "Agent") -> None:
    _divider(f"| INPUT → {agent_name}", _C.BLUE)
    print(f"  {content}")


def log_output(content: str, agent_name: str = "Agent") -> None:
    _divider(f"◀ FINISHED OUTPUT ← {agent_name}", _C.GREEN)
    print(f"  {content}\n")


def _msg_text(msg: Any) -> str:
    text = getattr(msg, "text", None)
    if isinstance(text, str) and text:
        return text

    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)

    return str(content) if content else ""


def _extract_reasoning(msg: Any) -> str:
    additional_kwargs = getattr(msg, "additional_kwargs", {})
    if isinstance(additional_kwargs, dict):
        reasoning = additional_kwargs.get("reasoning", {})
        if isinstance(reasoning, dict) and "summary" in reasoning:
            summary = reasoning["summary"]
            if isinstance(summary, str):
                return summary

    content_blocks = getattr(msg, "content_blocks", None)
    if content_blocks:
        for block in content_blocks:
            if isinstance(block, dict):
                if block.get("type") == "reasoning" and "reasoning" in block:
                    return str(block["reasoning"])
                if block.get("type") == "thinking" and "thinking" in block:
                    return str(block["thinking"])

    content = getattr(msg, "content", None)
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "reasoning" and "reasoning" in block:
                    return str(block["reasoning"])
                if block.get("type") == "thinking" and "thinking" in block:
                    return str(block["thinking"])

    return ""


def _stream_plain_chunk(
    chunk: Any,
    *,
    agent_name: str,
    streaming_text: bool,
    streaming_reasoning: bool,
) -> tuple[bool, bool, str]:
    """
    Handle standard LLM streaming from self.llm.stream(messages),
    where each item is a plain message chunk, not (mode, data).
    """
    final_text_piece = ""

    if not isinstance(chunk, AIMessageChunk):
        text = _msg_text(chunk)
        if text:
            if not streaming_text:
                if streaming_reasoning:
                    print(_C.RESET)
                    streaming_reasoning = False
                _divider(f"| {agent_name} | OUTPUT", _C.BLUE)
                sys.stdout.write(f"  {_C.CYAN}")
                streaming_text = True
            sys.stdout.write(text)
            sys.stdout.flush()
            final_text_piece += text
        return streaming_text, streaming_reasoning, final_text_piece

    reasoning_content = _extract_reasoning(chunk)
    if reasoning_content:
        if not streaming_reasoning:
            if streaming_text:
                print(_C.RESET)
                streaming_text = False
            _divider(f"| REASONING ← {agent_name}", _C.MAGENTA)
            sys.stdout.write(f"  {_C.DIM}{_C.GRAY}")
            streaming_reasoning = True
        sys.stdout.write(reasoning_content)
        sys.stdout.flush()

    if chunk.text:
        if not streaming_text:
            if streaming_reasoning:
                print(_C.RESET)
                streaming_reasoning = False
            _divider(f"| {agent_name} | OUTPUT", _C.BLUE)
            sys.stdout.write(f"  {_C.CYAN}")
            streaming_text = True
        sys.stdout.write(chunk.text)
        sys.stdout.flush()
        final_text_piece += chunk.text

    return streaming_text, streaming_reasoning, final_text_piece


def _handle_stream_sync(
    chunks: Iterator[Any],
    agent_name: Optional[str] = None,
) -> str:
    streaming_text = False
    streaming_reasoning = False
    current_node: str | None = None
    final_text = ""
    first_chunk = True

    spinner = _LoadingSpinner(f"Sending to {agent_name or 'Agent'}...")
    spinner.start()

    for item in chunks:
        if first_chunk:
            spinner.stop()
            first_chunk = False

        # --------------------------------------------------------------
        # Case 1: agent/langgraph stream -> item is (mode, data)
        # --------------------------------------------------------------
        if isinstance(item, tuple) and len(item) == 2:
            mode, data = item

            if mode == "messages":
                token, metadata = data
                node = metadata.get("langgraph_node", "")

                if node != current_node:
                    if streaming_text:
                        print(_C.RESET)
                        streaming_text = False
                    if streaming_reasoning:
                        print(_C.RESET)
                        streaming_reasoning = False
                    current_node = node

                if not isinstance(token, AIMessageChunk):
                    continue

                reasoning_content = _extract_reasoning(token)
                if reasoning_content:
                    if not streaming_reasoning:
                        if streaming_text:
                            print(_C.RESET)
                            streaming_text = False
                        _divider(f"| REASONING ← {agent_name or 'Agent'}", _C.MAGENTA)
                        sys.stdout.write(f"  {_C.DIM}{_C.GRAY}")
                        streaming_reasoning = True
                    sys.stdout.write(reasoning_content)
                    sys.stdout.flush()

                if token.text:
                    if not streaming_text:
                        if streaming_reasoning:
                            print(_C.RESET)
                            streaming_reasoning = False
                        _divider(f"| {agent_name or 'Agent'} | OUTPUT", _C.BLUE)
                        sys.stdout.write(f"  {_C.CYAN}")
                        streaming_text = True
                    sys.stdout.write(token.text)
                    sys.stdout.flush()
                    final_text += token.text

            elif mode == "updates":
                if streaming_text:
                    print(_C.RESET)
                    streaming_text = False
                if streaming_reasoning:
                    print(_C.RESET)
                    streaming_reasoning = False

                if not isinstance(data, dict):
                    continue

                for source, update in data.items():
                    if source == "__interrupt__":
                        _divider(f"| INTERRUPT ← {agent_name or 'Agent'}", _C.RED)
                        continue

                    if not isinstance(update, dict):
                        continue

                    messages = update.get("messages", [])
                    last_tool_name = "unknown_tool"

                    for msg in messages:
                        if isinstance(msg, AIMessage) and msg.tool_calls:
                            for tc in msg.tool_calls:
                                last_tool_name = tc["name"]
                                args_str = ", ".join(
                                    f"{k}={v!r}" for k, v in tc["args"].items()
                                )
                                _divider(
                                    f"| {agent_name or 'Agent'}, TOOL CALL: {tc['name']}",
                                    _C.BLUE,
                                )
                                _log_simple(
                                    f"{_C.YELLOW}{_C.BOLD}{tc['name']}"
                                    f"{_C.RESET}({_C.GRAY}{args_str}{_C.RESET})"
                                )

                        elif isinstance(msg, AIMessage):
                            text = _msg_text(msg)
                            if text.strip():
                                final_text = text

                        elif isinstance(msg, ToolMessage):
                            content = _msg_text(msg)
                            tool_name = getattr(msg, "name", None) or last_tool_name
                            _divider(
                                f"| TOOL, {tool_name} → {agent_name or 'Agent'}",
                                _C.BLUE,
                            )
                            _log_simple(f"{_C.GREEN}{content}{_C.RESET}")

            elif mode == "custom":
                if streaming_text:
                    print(_C.RESET)
                    streaming_text = False
                if streaming_reasoning:
                    print(_C.RESET)
                    streaming_reasoning = False
                _log_simple(f"{_C.MAGENTA}{str(data)}{_C.RESET}")

            continue

        # --------------------------------------------------------------
        # Case 2: plain model stream -> item is a normal chunk
        # --------------------------------------------------------------
        streaming_text, streaming_reasoning, text_piece = _stream_plain_chunk(
            item,
            agent_name=agent_name or "Agent",
            streaming_text=streaming_text,
            streaming_reasoning=streaming_reasoning,
        )
        final_text += text_piece

    if streaming_text:
        print(_C.RESET)
    if streaming_reasoning:
        print(_C.RESET)

    spinner.stop()
    return final_text


async def _handle_stream_async(
    chunks: AsyncIterator[Any],
    agent_name: Optional[str] = None,
) -> str:
    streaming_text = False
    streaming_reasoning = False
    current_node: str | None = None
    final_text = ""
    first_chunk = True

    spinner = _LoadingSpinner(f"Sending to {agent_name or 'Agent'}...")
    spinner.start()

    async for item in chunks:
        if first_chunk:
            spinner.stop()
            first_chunk = False

        if isinstance(item, tuple) and len(item) == 2:
            mode, data = item

            if mode == "messages":
                token, metadata = data
                node = metadata.get("langgraph_node", "")

                if node != current_node:
                    if streaming_text:
                        print(_C.RESET)
                        streaming_text = False
                    if streaming_reasoning:
                        print(_C.RESET)
                        streaming_reasoning = False
                    current_node = node

                if not isinstance(token, AIMessageChunk):
                    continue

                reasoning_content = _extract_reasoning(token)
                if reasoning_content:
                    if not streaming_reasoning:
                        if streaming_text:
                            print(_C.RESET)
                            streaming_text = False
                        _divider(f"| REASONING ← {agent_name or 'Agent'}", _C.MAGENTA)
                        sys.stdout.write(f"  {_C.DIM}{_C.GRAY}")
                        streaming_reasoning = True
                    sys.stdout.write(reasoning_content)
                    sys.stdout.flush()

                if token.text:
                    if not streaming_text:
                        if streaming_reasoning:
                            print(_C.RESET)
                            streaming_reasoning = False
                        _divider(
                            f"| {agent_name or 'Agent'} → STREAMING OUTPUT", _C.BLUE
                        )
                        sys.stdout.write(f"  {_C.CYAN}")
                        streaming_text = True
                    sys.stdout.write(token.text)
                    sys.stdout.flush()
                    final_text += token.text

            elif mode == "updates":
                if streaming_text:
                    print(_C.RESET)
                    streaming_text = False
                if streaming_reasoning:
                    print(_C.RESET)
                    streaming_reasoning = False

                if not isinstance(data, dict):
                    continue

                for source, update in data.items():
                    if source == "__interrupt__":
                        _divider(f"| INTERRUPT ← {agent_name or 'Agent'}", _C.RED)
                        continue

                    if not isinstance(update, dict):
                        continue

                    messages = update.get("messages", [])
                    last_tool_name = "unknown_tool"

                    for msg in messages:
                        if isinstance(msg, AIMessage) and msg.tool_calls:
                            for tc in msg.tool_calls:
                                last_tool_name = tc["name"]
                                args_str = ", ".join(
                                    f"{k}={v!r}" for k, v in tc["args"].items()
                                )
                                _divider(
                                    f"| TOOL CALL → {agent_name or 'Agent'} → {tc['name']}",
                                    _C.BLUE,
                                )
                                _log_simple(
                                    f"{_C.YELLOW}{_C.BOLD}{tc['name']}"
                                    f"{_C.RESET}({_C.GRAY}{args_str}{_C.RESET})"
                                )

                        elif isinstance(msg, AIMessage):
                            text = _msg_text(msg)
                            if text.strip():
                                final_text = text

                        elif isinstance(msg, ToolMessage):
                            content = _msg_text(msg)
                            tool_name = getattr(msg, "name", None) or last_tool_name
                            _divider(
                                f"| TOOL {tool_name} → {agent_name or 'Agent'}", _C.BLUE
                            )
                            _log_simple(f"{_C.GREEN}{content}{_C.RESET}")

            elif mode == "custom":
                if streaming_text:
                    print(_C.RESET)
                    streaming_text = False
                if streaming_reasoning:
                    print(_C.RESET)
                    streaming_reasoning = False
                _log_simple(f"{_C.MAGENTA}{str(data)}{_C.RESET}")

            continue

        streaming_text, streaming_reasoning, text_piece = _stream_plain_chunk(
            item,
            agent_name=agent_name or "Agent",
            streaming_text=streaming_text,
            streaming_reasoning=streaming_reasoning,
        )
        final_text += text_piece

    if streaming_text:
        print(_C.RESET)
    if streaming_reasoning:
        print(_C.RESET)

    spinner.stop()
    return final_text


def handle_stream(
    chunks: Union[Iterator[Any], AsyncIterator[Any]],
    agent_name: Optional[str] = None,
) -> str:
    if hasattr(chunks, "__anext__"):
        try:
            asyncio.get_running_loop()
            raise RuntimeError(
                "handle_stream called with async iterator from within async context. "
                "Use 'await handle_stream_async()' instead or call from sync context."
            )
        except RuntimeError as e:
            if "no running event loop" in str(e).lower():
                return asyncio.run(_handle_stream_async(chunks, agent_name))  # type: ignore
            raise
    return _handle_stream_sync(chunks, agent_name)  # type: ignore


async def handle_stream_async(
    chunks: AsyncIterator[Any],
    agent_name: Optional[str] = None,
) -> str:
    return await _handle_stream_async(chunks, agent_name)


def handle_stream_chunks(
    chunks: Iterator[Any],
    agent_name: str = "Agent",
    stream_mode: Sequence[str] | None = None,
    show_metadata: bool = False,
) -> str:
    return handle_stream(chunks, agent_name=agent_name)
