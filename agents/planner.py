from __future__ import annotations

from langchain_core.messages import SystemMessage, HumanMessage

from schemas.state import TravelState
from utils.config import get_llm
from utils.prompts import PLANNER_SYSTEM


class PlannerAgent:
    def __init__(self):
        self.llm = get_llm()

    def run(self, state: TravelState) -> TravelState:
        try:
            messages = [
                SystemMessage(content=PLANNER_SYSTEM),
                HumanMessage(content=state.user_request),
            ]

            response = self.llm.invoke(messages)

            state.plan = response.content
            state.status = "planned"

            return state

        except Exception as e:
            state.status = "failed"
            state.errors.append(f"Planner error: {str(e)}")
            return state
