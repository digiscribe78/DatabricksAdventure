"""Unity AI Gateway service-policy blocks, recognised and turned into in-world refusals.

A block comes back as HTTP 200 with finish_reason "content_filter" and the content
"This request was blocked by the '<policy>' service policy." (ChatDatabricks drops the
top-level databricks_service_policy object, so the name is read from the content.)
"""

import re
from dataclasses import dataclass

from rpg.turn import TurnEvent

_NAMED = re.compile(r"blocked by the '([^']+)' service policy")

# Stands in for the blocked words in the conversation history, so neither the model nor the
# jailbreak policy's conversation window ever sees them again.
REFUSED_PLACEHOLDER = "(The player's words were refused by the realm's wards.)"

POLICY_LABELS = {
    "block_jailbreak": "jailbreak screen",
    "block_unsafe_content": "unsafe-content screen",
    "stay_in_sparkia": "keeps the game in Sparkia",
}

_DEFAULT_REFUSAL = (
    "The air tightens. The old wards of Sparkia hum, and the words you meant to speak crumble to "
    "dust before they leave your lips. Whatever you were reaching for, the realm will not allow it. "
    "The moment passes, the world settles around you, and it waits to see what you will do next."
)
_REFUSALS = {
    "block_unsafe_content": (
        "A cold wind sweeps through and snuffs every candle at once. When the flames return, the "
        "thought you were holding has gone, carried off by the wards that keep Sparkia whole. Some "
        "deeds have no place in this realm. The world steadies, and it waits for what you will do next."
    ),
    "stay_in_sparkia": (
        "For a heartbeat the edges of the world blur, as if you had leaned too close to a painted "
        "backdrop. Then Sparkia snaps back into focus: the smell of smoke, the creak of timber, the "
        "weight of your pack. There is no world beyond this one here. What will you do next?"
    ),
}


@dataclass(frozen=True)
class Block:
    policy: str


def blocked_by(message) -> Block | None:
    """A gateway service-policy block, or None for a normal reply."""
    meta = getattr(message, "response_metadata", None) or {}
    if meta.get("finish_reason") != "content_filter":
        return None
    content = message.content if isinstance(message.content, str) else str(message.content)
    named = _NAMED.search(content)
    return Block(named.group(1) if named else "unknown")


def refusal_line(policy: str) -> str:
    """The canned in-world refusal, for when the model can't write one."""
    return _REFUSALS.get(policy, _DEFAULT_REFUSAL)


def guardrail_event(policy: str) -> TurnEvent:
    label = POLICY_LABELS.get(policy)
    name = f"{policy} ({label})" if label else policy
    return TurnEvent(type="guardrail", summary=f"Guardrail: {name} refused this turn", detail={"policy": policy})
