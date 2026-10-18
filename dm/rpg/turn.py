"""Structured output for a DM turn (spec §4.5).

The model writes only the prose (ComposeOutput). Code adds location, events and game state,
so the model can't misreport dice or state changes.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAX_NARRATION_WORDS = 400

EventType = Literal["roll", "attack", "lore", "memory", "state", "guardrail", "warning"]


class TurnEvent(BaseModel):
    type: EventType
    summary: str
    detail: dict = Field(default_factory=dict)


class ComposeOutput(BaseModel):
    narration: str = Field(description="The DM's narration for this turn, 40-200 words, second person.")
    choices: list[str] = Field(description="2 to 4 short suggested actions for the player.")
    allow_free_text: bool = True

    @field_validator("narration")
    @classmethod
    def _narration_ok(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("narration must not be blank")
        if len(v.split()) > MAX_NARRATION_WORDS:
            raise ValueError(f"narration exceeds {MAX_NARRATION_WORDS} words")
        return v

    @field_validator("choices")
    @classmethod
    def _choices_ok(cls, v: list[str]) -> list[str]:
        if not 2 <= len(v) <= 4:
            raise ValueError("choices must have 2 to 4 entries")
        if any(not c.strip() for c in v):
            raise ValueError("choices must not be blank")
        return [c.strip() for c in v]


class TurnOutput(ComposeOutput):
    location_id: str
    events: list[TurnEvent] = Field(default_factory=list)
    game_over: Literal["victory", "defeat"] | None = None

    @classmethod
    def from_compose(cls, c: ComposeOutput, location_id: str, events: list[TurnEvent]) -> "TurnOutput":
        return cls(**c.model_dump(), location_id=location_id, events=events)
