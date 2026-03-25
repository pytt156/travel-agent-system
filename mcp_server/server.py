from __future__ import annotations

import re
from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from data.trip_data import TRIP_OPTIONS

mcp = FastMCP("travel-agent-tools")


# ─────────────────────────────────────────────────────────────────────────────
# Hjälpfunktioner för att tolka fritext
# ─────────────────────────────────────────────────────────────────────────────


def _extract_budget(text: str) -> int | None:
    match = re.search(r"(\d{4,6})", text.replace(" ", ""))
    return int(match.group(1)) if match else None


# Svenska och engelska månadsnamn mappade till ett gemensamt värde
_MONTH_MAP: dict[str, str] = {
    "januari": "january",
    "january": "january",
    "februari": "february",
    "february": "february",
    "mars": "march",
    "march": "march",
    "april": "april",
    "maj": "may",
    "may": "may",
    "juni": "june",
    "june": "june",
    "juli": "july",
    "july": "july",
    "augusti": "august",
    "august": "august",
    "september": "september",
    "oktober": "october",
    "october": "october",
    "november": "november",
    "december": "december",
}


def _extract_month(text: str) -> str | None:
    text = text.lower()
    for word, value in _MONTH_MAP.items():
        if word in text:
            return value
    return None


# Nyckelord som tyder på att användaren vill till en europeisk huvudstad
_CAPITAL_KEYWORDS = [
    "europeisk huvudstad",
    "european capital",
    "capital",
    "huvudstad",
    "europe",
    "europa",
]


def _extract_destination_type(text: str) -> str:
    text_lower = text.lower()
    if any(kw in text_lower for kw in _CAPITAL_KEYWORDS):
        return "european_capital"
    # Default: vi har bara europeiska städer i trip_data,
    # så vi antar european_capital om inget annat anges
    return "european_capital"


# ─────────────────────────────────────────────────────────────────────────────
# MCP tools
# ─────────────────────────────────────────────────────────────────────────────


@mcp.tool()
def parse_request(
    user_request: Annotated[str, Field()],
) -> dict:
    return {
        "raw_request": user_request,
        "destination_type": _extract_destination_type(user_request),
        "month": _extract_month(user_request),
        "budget_sek": _extract_budget(user_request),
        "travelers": 2,
        "origin": "Stockholm",
    }


@mcp.tool()
def get_trip_options(
    destination_type: Annotated[str, Field()],
    month: Annotated[str | None, Field()],
    budget_sek: Annotated[int | None, Field()],
) -> list[dict]:
    results = []

    for trip in TRIP_OPTIONS:
        if destination_type == "european_capital" and not trip["is_european_capital"]:
            continue

        if month and trip["month"] != month:
            continue

        option = trip.copy()
        option["within_budget"] = (
            option["total_price"] <= budget_sek if budget_sek is not None else True
        )
        results.append(option)

    return results


@mcp.tool()
def select_best_option(
    trip_options: Annotated[list[dict], Field()],
    selection_strategy: Annotated[
        Literal["cheapest", "cheapest_within_budget"], Field()
    ] = "cheapest_within_budget",
) -> dict:
    if not trip_options:
        return {"selected_option": None, "reason": "No options"}

    if selection_strategy == "cheapest_within_budget":
        within = [t for t in trip_options if t.get("within_budget")]
        if within:
            best = min(within, key=lambda x: x["total_price"])
            return {"selected_option": best, "reason": "cheapest within budget"}

    best = min(trip_options, key=lambda x: x["total_price"])
    return {"selected_option": best, "reason": "cheapest overall"}


@mcp.tool()
def validate_option(
    parsed_request: Annotated[dict, Field()],
    selected_option: Annotated[dict, Field()],
) -> dict:
    issues = []

    if not selected_option:
        return {"approved": False, "issues": ["No option selected"]}

    if parsed_request[
        "destination_type"
    ] == "european_capital" and not selected_option.get("is_european_capital"):
        issues.append("Not a european capital")

    if (
        parsed_request["month"]
        and selected_option.get("month") != parsed_request["month"]
    ):
        issues.append("Wrong month")

    if (
        parsed_request["budget_sek"]
        and selected_option["total_price"] > parsed_request["budget_sek"]
    ):
        issues.append("Over budget")

    return {
        "approved": len(issues) == 0,
        "issues": issues,
    }


@mcp.tool()
def book_trip_stub(
    selected_option: Annotated[dict, Field()],
    approved_by_human: Annotated[bool, Field()],
) -> dict:
    if not approved_by_human:
        return {"status": "not_booked"}

    return {
        "status": "mock_booked",
        "trip": selected_option,
    }


if __name__ == "__main__":
    import asyncio

    asyncio.run(mcp.run_http_async(host="127.0.0.1", port=8000))
