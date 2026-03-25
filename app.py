from __future__ import annotations

from agents.planner import PlannerAgent
from agents.doer import DoerAgent
from agents.critic import CriticAgent
from agents.hitl import HumanAgent
from schemas.state import TravelState

from utils.streaming_utils import log_section


class MCPClient:
    def call_tool(self, tool_name: str, arguments: dict):
        from mcp_server.server import (
            parse_request,
            get_trip_options,
            select_best_option,
            validate_option,
            book_trip_stub,
        )

        tools = {
            "parse_request": parse_request,
            "get_trip_options": get_trip_options,
            "select_best_option": select_best_option,
            "validate_option": validate_option,
            "book_trip_stub": book_trip_stub,
        }

        return tools[tool_name](**arguments)


def main():
    user_request = input("What trip do you want?: ")

    state = TravelState(user_request=user_request)

    mcp = MCPClient()

    planner = PlannerAgent()
    doer = DoerAgent(mcp)
    critic = CriticAgent(mcp)
    human = HumanAgent()

    log_section("PLANNER")
    state = planner.run(state)
    if state.status == "failed":
        print(state.errors)
        return
    print(state.plan)

    log_section("DOER")
    state = doer.run(state)
    if state.status == "failed":
        print(state.errors)
        return
    print(state.doer_result)

    log_section("CRITIC")
    state = critic.run(state)
    if state.status == "failed":
        print(state.critic_result)
        return
    print(state.critic_result)

    log_section("HUMAN")
    state = human.run(state)
    if not state.human_approved:
        print("Not approved")
        return

    log_section("BOOKING")
    result = mcp.call_tool(
        "book_trip_stub",
        {
            "selected_option": state.selected_option,
            "approved_by_human": state.human_approved,
        },
    )

    print(result)


if __name__ == "__main__":
    main()
