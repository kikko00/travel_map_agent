from typing import Literal
from pydantic import BaseModel, Field
from .schemas import DayPlan, TripPlan


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    expected_version: int = Field(ge=1)


class PlanUpdate(BaseModel):
    plan: TripPlan
    expected_version: int = Field(ge=1)


class Intent(BaseModel):
    intent: Literal["answer", "clarify", "modify_plan"]
    target_days: list[int] = Field(default_factory=list)
    requires_search: bool = False
    clarification: str = ""
    poi_keywords: str = ""
    change_fields: list[Literal["description", "attractions", "meals", "hotel", "transportation", "accommodation"]] = Field(default_factory=lambda: ["attractions", "description"])


class AgentAnswer(BaseModel):
    reply: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    constraints_remove: list[str] = Field(default_factory=list)
    changes: list[DayPlan] = Field(default_factory=list)
