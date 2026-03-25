from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage

from schemas.state import TravelState
from utils.config import get_llm
from utils.prompts import CRITIC_SYSTEM


class CriticAgent:
    def __init__(self, mcp_client: Any):
        self.llm = get_llm()
        self.mcp = mcp_client

    def run(self, state: TravelState) -> TravelState:
        try:
            validation = self.mcp.call_tool(
                "validate_option",
                {
                    "parsed_request": state.parsed_request,
                    "selected_option": state.selected_option,
                },
            )

            messages = [
                SystemMessage(content=CRITIC_SYSTEM),
                HumanMessage(
                    content=f"""
Plan:
{state.plan}

Doer result:
{state.doer_result}

Validation result:
{validation}

Is the solution correct?
"""
                ),
            ]

            response = self.llm.invoke(messages)

            state.critic_result = {
                "validation": validation,
                "llm_review": response.content,
                "approved": validation.get("approved", False),
            }

            state.status = "reviewed" if state.critic_result["approved"] else "failed"

            return state

        except Exception as e:
            state.status = "failed"
            state.errors.append(f"Critic error: {str(e)}")
            return state
