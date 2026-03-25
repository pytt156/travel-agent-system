from __future__ import annotations

import re

from agents.critic import CriticAgent
from agents.doer import DoerAgent
from agents.hitl import HumanAgent
from agents.planner import PlannerAgent
from schemas.state import TravelState
from utils.middleware import run_middleware
from utils.streaming_utils import log_section

MAX_ITER = 3


class MCPClient:
    def call_tool(self, tool_name: str, arguments: dict):
        from mcp_server.server import (
            book_trip_stub,
            get_trip_options,
            parse_request,
            select_best_option,
            validate_option,
        )

        tools = {
            "parse_request": parse_request,
            "get_trip_options": get_trip_options,
            "select_best_option": select_best_option,
            "validate_option": validate_option,
            "book_trip_stub": book_trip_stub,
        }

        if tool_name not in tools:
            raise ValueError(f"Unknown tool: {tool_name!r}")

        result = tools[tool_name](**arguments)
        return run_middleware(tool_name, arguments, result)


_MONTHS = [
    "januari",
    "februari",
    "mars",
    "april",
    "maj",
    "juni",
    "juli",
    "augusti",
    "september",
    "oktober",
    "november",
    "december",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]


def check_info(state: TravelState) -> TravelState:
    req = state.user_request.lower()
    missing: list[str] = []

    if not any(m in req for m in _MONTHS):
        missing.append("which month you want to travel")

    if not re.search(r"\d{4,}", req.replace(" ", "")):
        missing.append("your budget in SEK (at least 4 digits, e.g. 20000)")

    if missing:
        log_section("INFO CHECKER")
        print("  More information is needed before planning the trip:\n")
        for item in missing:
            answer = input(f"  → {item}: ").strip()
            state.user_request += f" {answer}"
        print()

    return state


def main():
    user_request = input("What trip do you want to plan?: ").strip()
    state = TravelState(user_request=user_request)

    mcp = MCPClient()
    planner = PlannerAgent()
    doer = DoerAgent(mcp)
    critic = CriticAgent(mcp)
    human = HumanAgent()

    state = check_info(state)

    critic_approved = False

    for iteration in range(1, MAX_ITER + 1):
        if iteration > 1:
            log_section(f"RETRY {iteration - 1}/{MAX_ITER - 1}")
            state.plan = None
            state.doer_result = None
            state.critic_result = None
            state.selected_option = None
            state.status = "initialized"

        log_section(f"PLANNER  (iteration {iteration}/{MAX_ITER})")
        state = planner.run(state)
        if state.status == "failed":
            print(f"  Planner failed: {state.errors[-1]}")
            return

        log_section(f"DOER  (iteration {iteration}/{MAX_ITER})")
        state = doer.run(state)
        if state.status == "failed":
            print(f"  Doer failed: {state.errors[-1]}")
            return

        log_section(f"CRITIC  (iteration {iteration}/{MAX_ITER})")
        state = critic.run(state)

        if state.critic_result and state.critic_result.get("approved"):
            critic_approved = True
            break

        issues = state.critic_result.get("issues", []) if state.critic_result else []
        print(f"\n  Critic did not approve. Issues: {issues}")

        if iteration == MAX_ITER:
            print(f"\n  MAX_ITER ({MAX_ITER}) reached without approval. Aborting.")
            return

    if not critic_approved:
        return

    log_section("HUMAN IN THE LOOP")
    state = human.run(state)

    if not state.human_approved:
        print("\n  Trip rejected by user.")
        return

    log_section("BOOKING")
    result = mcp.call_tool(
        "book_trip_stub",
        {
            "selected_option": state.selected_option,
            "approved_by_human": state.human_approved,
        },
    )

    print(f"\n  Status : {result.get('status')}")
    if trip := result.get("trip"):
        print(f"  City   : {trip.get('city')}, {trip.get('country')}")
        print(f"  Price  : {trip.get('total_price')} SEK")
        print(f"  Link   : {trip.get('booking_link')}")


if __name__ == "__main__":
    main()
