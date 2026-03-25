from __future__ import annotations

from langchain.agents import create_agent

from schemas.state import TravelState
from utils.config import get_llm
from utils.prompts import PLANNER_SYSTEM
from utils.streaming_utils import STREAM_MODES, handle_stream


class PlannerAgent:
    def __init__(self):
        self.agent = self._build_agent()

    def _build_agent(self):
        model = get_llm()

        agent = create_agent(
            model=model,
            tools=[],
            system_prompt=PLANNER_SYSTEM,
            name="Planner",
        )
        return agent

    def run(self, state: TravelState) -> TravelState:
        try:
            chunks = self.agent.stream(
                {"messages": [{"role": "user", "content": state.user_request}]},
                stream_mode=STREAM_MODES,
            )

            final_text = handle_stream(chunks, agent_name="Planner")

            state.plan = final_text
            state.status = "planned"
            return state

        except Exception as e:
            state.status = "failed"
            state.errors.append(f"Planner error: {str(e)}")
            return state
