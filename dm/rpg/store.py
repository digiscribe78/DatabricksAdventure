"""Where game state lives. GameStore is the contract, and InMemoryStore backs tests and dev without Lakebase."""

from pathlib import Path
from typing import Protocol

import yaml

from rpg.state import GameState, NpcCard, NpcPresence
from rpg.world import START_LOCATION_ID, Character, new_character


class GameStore(Protocol):
    def create_adventure(self, session_id: str, player_id: str, name: str, archetype: str) -> GameState: ...
    def load(self, session_id: str) -> GameState | None: ...
    def owner(self, session_id: str) -> str | None: ...
    def commit(self, session_id: str, state: GameState) -> None: ...
    def list_adventures(self, player_id: str) -> list[dict]: ...
    def delete_adventure(self, session_id: str) -> None: ...
    def seed_npcs(self, cards: list[NpcCard]) -> None: ...


def load_npc_cards(directory: str | Path) -> list[NpcCard]:
    return [NpcCard.model_validate(yaml.safe_load(p.read_text())) for p in sorted(Path(directory).glob("*.yaml"))]


class InMemoryStore:
    def __init__(self, cards: list[NpcCard] = ()):
        self._cards: dict[str, NpcCard] = {c.npc_id: c for c in cards}
        self._adventures: dict[str, dict] = {}

    def seed_npcs(self, cards: list[NpcCard]) -> None:
        self._cards.update({c.npc_id: c for c in cards})

    def create_adventure(self, session_id, player_id, name, archetype):
        if session_id in self._adventures:
            raise ValueError(f"adventure already exists for session {session_id}")
        self._adventures[session_id] = {
            "player_id": player_id, "character": new_character(name, archetype).model_dump(),
            "location_id": START_LOCATION_ID, "flags": {}, "dispositions": {}, "status": "active",
        }
        return self.load(session_id)

    def load(self, session_id):
        a = self._adventures.get(session_id)
        if a is None:
            return None
        npcs = [
            NpcPresence(**card.model_dump(), disposition=a["dispositions"].get(card.npc_id, 0))
            for card in sorted(self._cards.values(), key=lambda c: c.npc_id)
            if card.home_location_id == a["location_id"]
        ]
        return GameState(character=Character.model_validate(a["character"]), location_id=a["location_id"],
                         flags=dict(a["flags"]), npcs=npcs)

    def owner(self, session_id):
        a = self._adventures.get(session_id)
        return a["player_id"] if a else None

    def commit(self, session_id, state):
        a = self._adventures.get(session_id)
        if a is None:
            raise LookupError(f"no adventure for session {session_id}")
        a["character"] = state.character.model_dump()
        a["location_id"] = state.location_id
        a["flags"].update(state.flags)
        a["dispositions"].update({n.npc_id: n.disposition for n in state.npcs})

    def list_adventures(self, player_id):
        return [
            {"session_id": sid, "name": a["character"]["name"], "archetype": a["character"]["archetype"],
             "location_id": a["location_id"], "status": a["status"]}
            for sid, a in self._adventures.items() if a["player_id"] == player_id
        ]

    def delete_adventure(self, session_id):
        self._adventures.pop(session_id, None)
