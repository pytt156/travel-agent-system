from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


WorkflowStatus = Literal[
    "initialized",
    "planned",
    "executed",
    "reviewed",
    "completed",
    "failed",
]


class TravelState(BaseModel):
    user_request: str

    plan: str | None = None
    parsed_request: dict[str, Any] | None = None
    trip_options: list[dict[str, Any]] = Field(default_factory=list)
    selected_option: dict[str, Any] | None = None
    doer_result: dict[str, Any] | None = None
    critic_result: dict[str, Any] | None = None
    human_approved: bool | None = None
    final_result: dict[str, Any] | None = None

    status: WorkflowStatus = "initialized"
    errors: list[str] = Field(default_factory=list)
