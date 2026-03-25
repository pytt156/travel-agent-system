from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage

from schemas.state import TravelState
from utils.config import get_llm
from utils.prompts import DOER_SYSTEM


class DoerAgent:
    def __init__(self, mcp_client: Any):
        self.llm = get_llm()
        self.mcp = mcp_client

    def run(self, state: TravelState) -> TravelState:
        try:
            parsed = self.mcp.call_tool(
                "parse_request",
                {"user_request": state.user_request},
            )
            state.parsed_request = parsed

            options = self.mcp.call_tool(
                "get_trip_options",
                {
                    "destination_type": parsed["destination_type"],
                    "month": parsed["month"],
                    "budget_sek": parsed["budget_sek"],
                },
            )
            state.trip_options = options

            messages = [
                SystemMessage(content=DOER_SYSTEM),
                HumanMessage(
                    content=f"""
Plan:
{state.plan}

Parsed request:
{parsed}

Trip options:
{options}

Select the best option and explain briefly.
"""
                ),
            ]

            response = self.llm.invoke(messages)

            state.doer_result = {
                "raw_output": response.content,
                "selected_option": options[0] if options else None,
            }

            state.selected_option = state.doer_result["selected_option"]
            state.status = "executed"

            return state

        except Exception as e:
            state.status = "failed"
            state.errors.append(f"Doer error: {str(e)}")
            return state
