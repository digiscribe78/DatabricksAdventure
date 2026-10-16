# Milestone 3a: Game State in Lakebase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The adventure becomes a real save game. The player starts a `new_game` (name and archetype), and their character sheet, inventory, location, quest flags and NPC dispositions persist in Lakebase. The DM changes the world only through **staged tools**: `update_character`, `move_to`, `set_quest_flag`, `set_npc_disposition` and `enemy_attack`. They are committed in **one transaction per turn**, and every change shows up as a 💾 turn event. Combat gets `resolve_attack` and `enemy_attack`. NPC character cards (SillyTavern-style) are loaded into the DM's context whenever the NPC is present.

**Scope split.** Spec milestone 3 is split in two:
- **M3a (this plan): game state.** Everything runs locally under `agentbricks dev`.
- **M3b (next plan): managed session and memory stores.** That includes the first `agentbricks deploy` to Agent Runtime, service principal grants, the memory "dreaming" pipeline, and checking workspace tracing.

The reason for the split: `agentbricks dev` runs sessions in-process with memory switched off, so M3b can't be tested without deploying.

**Architecture:**
- **Pure game logic** in `rpg/`:
  - `rpg.state` holds the `GameState` model, typed change records and a pure `apply_changes()`. It covers HP clamping, the downed rule, inventory, flags, dispositions and moves.
  - `rpg.store` holds a `GameStore` protocol and an `InMemoryStore`.
- **`agent.pgstore.PostgresStore`** implements the same protocol on Lakebase, using psycopg 3 and an OAuth token from `w.postgres.generate_database_credential`. One contract test suite runs against both stores.
- **The graph** becomes `load_state (store) → dm_reason ⇄ tools → commit_state (store, one txn) → compose`.
- **The adapter** creates the adventure from `new_game`, keyed by the invocation's `session_id`.

**Tech Stack:**
- Lakebase Autoscaling (`postgres_projects` bundle resource, PG 17), psycopg 3.3
- LangGraph `Command` updates from tools (`InjectedToolCallId`), Pydantic v2 discriminated unions
- The existing `dm/` and `pipelines/` stacks

**Spec:** `docs/superpowers/specs/2026-10-16-databricks-rpg-design.md`, §5 (rules), §7 (state), §10 (errors) and §15.3. Builds on the merged M2.

## Global Constraints

- Python `>=3.11` and `uv`. The dev profile is `brickbots` and the catalog is `serverless_stable_brickbots_catalog`, set on the command line or in gitignored `dm/.env`. Tracked code and config never hard-code a profile, host, catalog, token or email.
- Lakebase project id `databricks-adventure`, branch `production`, endpoint `primary`, database `databricks_postgres`, schema **`rpg`**.
- Env vars for Lakebase, used by the Apps-injected pattern and by local dev: `PGHOST`, `PGPORT` (default 5432), `PGDATABASE`, `PGUSER`, `LAKEBASE_ENDPOINT`. **When `PGHOST` is unset, the agent falls back to an `InMemoryStore`**, so dev without Lakebase still works.
- **The agent is the only writer of game state, and all writes happen in `commit_state`, in one transaction per turn.** Tools only *stage* changes.
- **The DM never invents numbers.** Player modifiers and defence come from state. Enemy stats come from the model, because they're world facts from the bestiary. HP changes from combat are applied by code.
- Rules, spec §5:
  - d20 + modifier ≥ DC.
  - Attack: d20 + Might (weapons) or Wits (spells) ≥ defence. Damage is a die from `(4, 6, 8, 10, 12)` plus a bonus of 0–5.
  - **Player defence = 10 + max(Might, Wits).**
  - **Downed at 0 HP:** move to `medallion-inn`, HP = max_hp // 2, gold = gold // 2, and increment the flag `times_downed`.
  - Disposition is clamped to −3…+3.
- Quest flags are snake_case slugs matching `^[a-z][a-z0-9_]{0,47}$`, with values of 80 characters at most. This is free-form in sandbox mode; the campaign design later makes the list canonical.
- Session = adventure: `rpg.adventures.id` **is** the invocation `session_id`.
- Commit messages end with `Co-authored-by: Isaac <no-reply@databricks.com>`.

**Spec deltas (recorded in Task 7):**
1. M3 is split into M3a and M3b (§15).
2. `adventures.id` is the session id, so there's no separate `session_id` column (§7).
3. Enemy HP is tracked in narration only for v1 (§5).
4. NPC cards exist only for NPCs whose home is a built location (§7).
5. **The UC-function promotion of `roll_check` is still open.** It's flagged for Mike in the plan handoff, not built here.

## Review Focus

1. **The model calls `move_to` with a non-exit or unknown location**, or `set_npc_disposition` for an NPC who isn't there. The tool returns an error naming the valid options, nothing is staged, and the turn completes. Pinned in Task 4.
2. **Lakebase is unreachable or the commit fails mid-turn.** The player gets an in-world "nothing stuck" turn, the stored state is unchanged, and the failed turn's tool messages are removed from history so a retry starts clean. Pinned in Task 5.
3. **Crash-recovery replays a `new_game` invocation.** It continues the existing adventure instead of failing with "already exists". Pinned in Task 6.
4. **HP drops to 0 or below** (a big hit, or several hits in one turn). The downed rule applies once, HP never goes negative, and the character wakes at the inn. Pinned in Task 1.
5. **A long session outlives the 1-hour Lakebase token.** The token is refreshed before it expires, not reused after. Pinned in Task 3.

---

## File structure (end of M3a)

```
content/npcs/marta-quill.yaml, content/npcs/the-sweeper.yaml     NPC character cards
resources/lakebase.yml                                            postgres_projects: databricks-adventure
scripts/lakebase_env.sh                                           prints PG* / LAKEBASE_ENDPOINT exports
Makefile                                                          (modified) + db target; deploy runs db
dm/rpg/rules.py      (modified) + AttackResult, DAMAGE_DICE, resolve_attack()
dm/rpg/world.py      (modified) + Character.defence
dm/rpg/state.py      NpcCard, NpcPresence, GameState, CharacterChange, FlagChange, DispositionChange, MoveChange, apply_changes()
dm/rpg/store.py      GameStore (Protocol), InMemoryStore, load_npc_cards()
dm/rpg/schema.sql    rpg schema DDL
dm/agent/pgstore.py  PostgresStore, migrate(), token cache, CLI: python -m agent.pgstore migrate <npcs_dir>
dm/agent/tools/state_tools.py   update_character, set_quest_flag, set_npc_disposition, move_to
dm/agent/tools/dice.py          (modified) + resolve_attack, enemy_attack
dm/agent/dm_graph.py            (modified) store-backed load_state, commit_state, state/attack events
dm/agent/prompts.py             (modified) render_dm_system(GameState) with NPC cards, flags, exits, tool rules
dm/agent/agent.py               (modified) game_store(), store passed to the graph
dm/runtime/adapter.py           (modified) new_game handling and the adventure precondition
dm/scripts/smoke_turns.sh       (modified) new_game opening, location and 💾/⚔ events
dm/tests/test_state.py, test_store.py, test_pgstore.py, test_state_tools.py, (modified) test_rules.py, test_world.py, test_dm_graph.py, test_agent.py
```

---

### Task 1: Combat rules, player defence and pure state changes

**Files:**
- Modify: `dm/rpg/rules.py`, `dm/rpg/world.py`
- Create: `dm/rpg/state.py`
- Test: `dm/tests/test_rules.py` (append), `dm/tests/test_world.py` (append), `dm/tests/test_state.py`

**Interfaces:**
- Produces:
  - `rpg.rules.DAMAGE_DICE = (4, 6, 8, 10, 12)`
  - `@dataclass(frozen=True) AttackResult(roll, modifier, total, defence, hit: bool, damage_roll, damage)` with `.to_dict()`
  - `rpg.rules.resolve_attack(modifier: int, defence: int, damage_die: int, damage_bonus: int, rng) -> AttackResult`. It raises `ValueError` if `damage_die ∉ DAMAGE_DICE`, if `defence ∉ [5, 25]` or if `damage_bonus ∉ [0, 5]`. It rolls the d20 first, then the damage die only on a hit.
  - `Character.defence` (a property) = `10 + max(might, wits)`
  - `rpg.state`:
    - `NpcCard(npc_id, name, persona, speech_style, secrets, home_location_id)`
    - `NpcPresence(NpcCard)` adds `disposition: int = 0`
    - `GameState(character: Character, location_id: str, flags: dict[str, str] = {}, npcs: list[NpcPresence] = [])`
    - Change models with discriminator `kind`:
      - `CharacterChange(kind="character", hp_delta=0, xp_delta=0, gold_delta=0, items_add=[], items_remove=[])`
      - `FlagChange(kind="flag", flag, value)`
      - `DispositionChange(kind="disposition", npc_id, delta)`
      - `MoveChange(kind="move", location_id)`
    - `FLAG_PATTERN`
    - `apply_changes(state: GameState, changes: list[dict]) -> tuple[GameState, list[str]]`. It's pure: it returns a new state plus human-readable summaries, applies changes in order, and raises `pydantic.ValidationError` on a malformed change.

- [ ] **Step 1: Write the failing tests**

Append to `dm/tests/test_rules.py`:
```python
from rpg.rules import DAMAGE_DICE, resolve_attack


class SeqRng(random.Random):
    """randint returns the given values in order."""

    def __init__(self, *values):
        super().__init__(0)
        self.values = list(values)

    def randint(self, a, b):
        return self.values.pop(0)


def test_attack_hits_and_rolls_damage():
    r = resolve_attack(modifier=3, defence=12, damage_die=6, damage_bonus=2, rng=SeqRng(9, 4))
    assert (r.roll, r.total, r.hit, r.damage_roll, r.damage) == (9, 12, True, 4, 6)


def test_attack_miss_rolls_no_damage():
    rng = SeqRng(2)
    r = resolve_attack(modifier=0, defence=12, damage_die=6, damage_bonus=2, rng=rng)
    assert (r.hit, r.damage_roll, r.damage) == (False, 0, 0)
    assert rng.values == []


@pytest.mark.parametrize("kwargs", [
    {"damage_die": 7}, {"damage_die": 20}, {"defence": 4}, {"defence": 26},
    {"damage_bonus": -1}, {"damage_bonus": 6},
])
def test_attack_rejects_out_of_range_inputs(kwargs):
    args = {"modifier": 0, "defence": 12, "damage_die": 6, "damage_bonus": 0, **kwargs}
    with pytest.raises(ValueError):
        resolve_attack(rng=SeqRng(10, 1), **args)


def test_damage_dice_constant():
    assert DAMAGE_DICE == (4, 6, 8, 10, 12)
```

Append to `dm/tests/test_world.py`:
```python
def test_defence_is_ten_plus_best_of_might_and_wits():
    assert new_character("A", "warrior").defence == 13
    assert new_character("B", "mage").defence == 13
    assert new_character("C", "bard").defence == 11
```

`dm/tests/test_state.py`:
```python
import pytest
from pydantic import ValidationError
from rpg.state import GameState, NpcPresence, apply_changes
from rpg.world import new_character

MARTA = NpcPresence(npc_id="marta-quill", name="Marta Quill", persona="p", speech_style="s",
                    secrets="x", home_location_id="medallion-inn", disposition=0)


def state(**kw):
    base = {"character": new_character("Brannoc", "warrior"), "location_id": "medallion-inn", "npcs": [MARTA]}
    return GameState(**{**base, **kw})


def test_hp_change_clamps_to_max_and_summarises():
    s, notes = apply_changes(state(), [{"kind": "character", "hp_delta": 5}])
    assert s.character.hp == 18
    s, notes = apply_changes(s, [{"kind": "character", "hp_delta": -4}])
    assert s.character.hp == 14 and "HP 18 → 14" in notes


def test_reaching_zero_hp_downs_character_once():
    s, notes = apply_changes(state(location_id="delta-crossing", npcs=[]),
                             [{"kind": "character", "hp_delta": -10}, {"kind": "character", "hp_delta": -40}])
    c = s.character
    assert (c.hp, c.gold, s.location_id) == (9, 6, "medallion-inn")
    assert s.flags["times_downed"] == "1"
    assert sum("downed" in n for n in notes) == 1


def test_items_add_remove_and_missing_item_noted():
    s, notes = apply_changes(state(), [{"kind": "character", "items_add": ["lantern"], "items_remove": ["shield", "crown"]}])
    assert "lantern" in s.character.inventory and "shield" not in s.character.inventory
    assert "+lantern" in notes and "-shield" in notes
    assert any("crown" in n and "not carried" in n for n in notes)


def test_gold_cannot_go_negative():
    s, notes = apply_changes(state(), [{"kind": "character", "gold_delta": -50}])
    assert s.character.gold == 0
    assert any("only had 12" in n for n in notes)


def test_xp_and_flag():
    s, notes = apply_changes(state(), [{"kind": "character", "xp_delta": 5}, {"kind": "flag", "flag": "met_sweeper", "value": "yes"}])
    assert s.character.xp == 5 and s.flags == {"met_sweeper": "yes"}
    assert "XP +5" in notes and "flag met_sweeper = yes" in notes


def test_disposition_clamps():
    s, notes = apply_changes(state(), [{"kind": "disposition", "npc_id": "marta-quill", "delta": 5}])
    assert s.npcs[0].disposition == 3 and "Marta Quill: 0 → 3" in notes


def test_move_to_exit_and_reject_non_exit():
    s, notes = apply_changes(state(), [{"kind": "move", "location_id": "delta-crossing"}])
    assert s.location_id == "delta-crossing" and "moved to The Delta Crossing" in notes
    s2, notes2 = apply_changes(state(), [{"kind": "move", "location_id": "unity-archive"}])
    assert s2.location_id == "medallion-inn" and any("cannot reach" in n for n in notes2)


def test_input_state_is_not_mutated():
    original = state()
    apply_changes(original, [{"kind": "character", "hp_delta": -4, "items_add": ["x"]}])
    assert original.character.hp == 18 and "x" not in original.character.inventory


@pytest.mark.parametrize("bad", [
    {"kind": "teleport"},
    {"kind": "flag", "flag": "Bad Flag!", "value": "x"},
    {"kind": "flag", "flag": "ok", "value": "x" * 81},
])
def test_malformed_changes_rejected(bad):
    with pytest.raises(ValidationError):
        apply_changes(state(), [bad])
```

- [ ] **Step 2: Run them and check they fail**

Run: `cd dm && uv run pytest tests/test_rules.py tests/test_world.py tests/test_state.py -q`
Expected: collection fails with `ImportError: cannot import name 'DAMAGE_DICE'` and `ModuleNotFoundError: No module named 'rpg.state'`.

- [ ] **Step 3: Implement the rules and defence**

Append to `dm/rpg/rules.py`:
```python
DAMAGE_DICE = (4, 6, 8, 10, 12)


@dataclass(frozen=True)
class AttackResult:
    roll: int
    modifier: int
    total: int
    defence: int
    hit: bool
    damage_roll: int
    damage: int

    def to_dict(self) -> dict:
        return asdict(self)


def resolve_attack(modifier: int, defence: int, damage_die: int, damage_bonus: int, rng: random.Random) -> AttackResult:
    """One combat exchange: d20 + modifier against defence. A hit deals damage_die + damage_bonus."""
    if damage_die not in DAMAGE_DICE:
        raise ValueError(f"damage_die must be one of {DAMAGE_DICE}, got {damage_die}")
    if not 5 <= defence <= 25:
        raise ValueError(f"defence must be between 5 and 25, got {defence}")
    if not 0 <= damage_bonus <= 5:
        raise ValueError(f"damage_bonus must be between 0 and 5, got {damage_bonus}")
    roll = roll_d20(rng)
    total = roll + modifier
    hit = total >= defence
    damage_roll = rng.randint(1, damage_die) if hit else 0
    return AttackResult(roll, modifier, total, defence, hit, damage_roll, damage_roll + damage_bonus if hit else 0)
```
In `dm/rpg/world.py`, add this to the `Character` class, below `modifier`:
```python
    @property
    def defence(self) -> int:
        return 10 + max(self.might, self.wits)
```

- [ ] **Step 4: Implement `rpg.state`**

`dm/rpg/state.py`:
```python
"""Game state and the changes the DM may stage. apply_changes is pure: same input, same output."""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

from rpg.world import LOCATIONS, START_LOCATION_ID, Character

FLAG_PATTERN = r"^[a-z][a-z0-9_]{0,47}$"


class NpcCard(BaseModel):
    npc_id: str
    name: str
    persona: str
    speech_style: str
    secrets: str
    home_location_id: str


class NpcPresence(NpcCard):
    disposition: int = 0


class GameState(BaseModel):
    character: Character
    location_id: str
    flags: dict[str, str] = Field(default_factory=dict)
    npcs: list[NpcPresence] = Field(default_factory=list)


class CharacterChange(BaseModel):
    kind: Literal["character"] = "character"
    hp_delta: int = 0
    xp_delta: int = 0
    gold_delta: int = 0
    items_add: list[str] = Field(default_factory=list)
    items_remove: list[str] = Field(default_factory=list)


class FlagChange(BaseModel):
    kind: Literal["flag"] = "flag"
    flag: str = Field(pattern=FLAG_PATTERN)
    value: str = Field(max_length=80)


class DispositionChange(BaseModel):
    kind: Literal["disposition"] = "disposition"
    npc_id: str
    delta: int


class MoveChange(BaseModel):
    kind: Literal["move"] = "move"
    location_id: str


Change = Annotated[Union[CharacterChange, FlagChange, DispositionChange, MoveChange], Field(discriminator="kind")]
_CHANGES = TypeAdapter(list[Change])


def _apply_character(state: GameState, ch: CharacterChange, notes: list[str]) -> None:
    c = state.character
    if ch.hp_delta:
        new_hp = max(0, min(c.max_hp, c.hp + ch.hp_delta))
        notes.append(f"HP {c.hp} → {new_hp}")
        c.hp = new_hp
    if ch.xp_delta:
        c.xp = max(0, c.xp + ch.xp_delta)
        notes.append(f"XP {ch.xp_delta:+d}")
    if ch.gold_delta:
        if c.gold + ch.gold_delta < 0:
            notes.append(f"wanted {-ch.gold_delta} gold but only had {c.gold}")
        new_gold = max(0, c.gold + ch.gold_delta)
        notes.append(f"Gold {c.gold} → {new_gold}")
        c.gold = new_gold
    for item in ch.items_add:
        c.inventory.append(item)
        notes.append(f"+{item}")
    for item in ch.items_remove:
        if item in c.inventory:
            c.inventory.remove(item)
            notes.append(f"-{item}")
        else:
            notes.append(f"{item} not carried")


def _downed(state: GameState, notes: list[str]) -> None:
    c = state.character
    c.hp = c.max_hp // 2
    c.gold = c.gold // 2
    state.location_id = START_LOCATION_ID
    state.flags["times_downed"] = str(int(state.flags.get("times_downed", "0")) + 1)
    notes.append(f"downed: woke at {LOCATIONS[START_LOCATION_ID].name} with HP {c.hp} and {c.gold} gold")


def apply_changes(state: GameState, changes: list[dict]) -> tuple[GameState, list[str]]:
    parsed = _CHANGES.validate_python(changes)
    new = state.model_copy(deep=True)
    notes: list[str] = []
    for ch in parsed:
        if isinstance(ch, CharacterChange):
            _apply_character(new, ch, notes)
            if new.character.hp == 0:
                _downed(new, notes)
        elif isinstance(ch, FlagChange):
            new.flags[ch.flag] = ch.value
            notes.append(f"flag {ch.flag} = {ch.value}")
        elif isinstance(ch, DispositionChange):
            for npc in new.npcs:
                if npc.npc_id == ch.npc_id:
                    after = max(-3, min(3, npc.disposition + ch.delta))
                    notes.append(f"{npc.name}: {npc.disposition} → {after}")
                    npc.disposition = after
        elif isinstance(ch, MoveChange):
            here = LOCATIONS[new.location_id]
            if ch.location_id in here.exits and ch.location_id in LOCATIONS:
                new.location_id = ch.location_id
                notes.append(f"moved to {LOCATIONS[ch.location_id].name}")
            else:
                notes.append(f"cannot reach {ch.location_id} from {here.name}")
    return new, notes
```

- [ ] **Step 5: Run the tests and check they pass**

Run: `cd dm && uv run pytest -q`
Expected: everything passes, including 9 new rules tests, 1 new world test and 11 state tests.

- [ ] **Step 6: Commit**

```bash
git add dm/rpg dm/tests/test_rules.py dm/tests/test_world.py dm/tests/test_state.py
git commit -m "feat(rpg): add attack rules, player defence and pure game-state changes

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 2: The `GameStore` protocol, `InMemoryStore` and NPC cards

**Files:**
- Create: `content/npcs/marta-quill.yaml`, `content/npcs/the-sweeper.yaml`, `dm/rpg/store.py`
- Test: `dm/tests/test_store.py` (the contract suite; its postgres variant is skipped until Task 3)

**Interfaces:**
- Consumes: `rpg.state.GameState`, `NpcCard`, `NpcPresence` and `rpg.world.new_character`, `START_LOCATION_ID`
- Produces:
  - `rpg.store.GameStore` (`typing.Protocol`):
    - `create_adventure(session_id: str, player_id: str, name: str, archetype: str) -> GameState`. Raises `ValueError` if the session already has an adventure.
    - `load(session_id: str) -> GameState | None`. The returned `npcs` are the cards whose `home_location_id == location_id`, with this character's disposition (default 0).
    - `commit(session_id: str, state: GameState) -> None`. Persists the character's hp, xp, gold, location and inventory, upserts flags, and upserts the dispositions of the NPCs in `state.npcs`. Raises `LookupError` for an unknown session.
    - `list_adventures(player_id: str) -> list[dict]`, with keys `session_id, name, archetype, location_id, status`
    - `delete_adventure(session_id: str) -> None`
    - `seed_npcs(cards: list[NpcCard]) -> None`
  - `rpg.store.InMemoryStore(cards: list[NpcCard] = ())`
  - `rpg.store.load_npc_cards(directory: str | Path) -> list[NpcCard]`, which reads `*.yaml` sorted by filename

- [ ] **Step 1: Write the NPC cards**

`content/npcs/marta-quill.yaml`:
```yaml
npc_id: marta-quill
name: Marta Quill
home_location_id: medallion-inn
persona: >-
  Wiry, iron-grey innkeeper of the Medallion Inn. Sharp-eyed, warm to honest travellers,
  ruthless with cheats. Knows everyone's business and trades rumours for good stories or fair coin.
speech_style: >-
  Brisk, dry and motherly. Calls people "love" or "stranger". Short sentences, and she taps the
  side of her nose when sharing a secret.
secrets: >-
  She is frightened for her old friend Keeper Aldric of the Unity Archive, and she has a key to a
  cellar door that leads to running water nobody else knows about.
```

`content/npcs/the-sweeper.yaml`:
```yaml
npc_id: the-sweeper
name: The Sweeper
home_location_id: delta-crossing
persona: >-
  Tall, silent ferryman of the Delta Crossing in a salt-stained coat. Never gives a name. Keeps the
  crossing clear of old wreckage and older ghosts, and charges exactly two gold a crossing.
speech_style: >-
  Few words, low and unhurried. Speaks of time and tidiness: "Leave it too long and it must be swept."
  Never haggles.
secrets: >-
  He can see which day each current of the river carries, and he knows the river has been running
  backwards because something upstream is hoarding the old currents.
```

- [ ] **Step 2: Write the failing contract tests**

`dm/tests/test_store.py`:
```python
"""GameStore contract: every store implementation must pass these."""

import os
import uuid
from pathlib import Path

import pytest
from rpg.state import apply_changes
from rpg.store import InMemoryStore, load_npc_cards

NPCS = Path(__file__).resolve().parents[2] / "content" / "npcs"


@pytest.fixture(params=["memory", "postgres"])
def store(request):
    if request.param == "memory":
        yield InMemoryStore(load_npc_cards(NPCS))
        return
    if not os.getenv("PGHOST"):
        pytest.skip("PGHOST not set; Lakebase contract tests need a live database")
    from agent.pgstore import PostgresStore

    s = PostgresStore.from_env()
    s.seed_npcs(load_npc_cards(NPCS))
    yield s


@pytest.fixture
def sid(store):
    session_id = f"test-{uuid.uuid4()}"
    yield session_id
    store.delete_adventure(session_id)


def test_load_npc_cards():
    cards = load_npc_cards(NPCS)
    assert [c.npc_id for c in cards] == ["marta-quill", "the-sweeper"]


def test_create_then_load(store, sid):
    created = store.create_adventure(sid, "player-1", "Brannoc", "warrior")
    loaded = store.load(sid)
    assert loaded == created
    assert loaded.character.name == "Brannoc" and loaded.character.hp == 18
    assert loaded.location_id == "medallion-inn" and loaded.flags == {}
    assert [(n.npc_id, n.disposition) for n in loaded.npcs] == [("marta-quill", 0)]


def test_create_twice_rejected(store, sid):
    store.create_adventure(sid, "player-1", "Brannoc", "warrior")
    with pytest.raises(ValueError):
        store.create_adventure(sid, "player-1", "Other", "bard")


def test_load_unknown_is_none(store):
    assert store.load(f"missing-{uuid.uuid4()}") is None


def test_commit_unknown_session_raises(store):
    game = InMemoryStore(load_npc_cards(NPCS)).create_adventure("x", "p", "A", "bard")
    with pytest.raises(LookupError):
        store.commit(f"missing-{uuid.uuid4()}", game)


def test_commit_persists_all_kinds_of_change(store, sid):
    game = store.create_adventure(sid, "player-1", "Brannoc", "warrior")
    game, _ = apply_changes(game, [
        {"kind": "character", "hp_delta": -4, "gold_delta": -2, "xp_delta": 5, "items_add": ["lantern", "rope"]},
        {"kind": "flag", "flag": "met_marta", "value": "yes"},
        {"kind": "disposition", "npc_id": "marta-quill", "delta": 1},
        {"kind": "move", "location_id": "delta-crossing"},
    ])
    store.commit(sid, game)
    loaded = store.load(sid)
    c = loaded.character
    assert (c.hp, c.gold, c.xp) == (14, 10, 5)
    assert sorted(c.inventory) == sorted(["longsword (d6+2)", "shield", "rope", "lantern", "rope"])
    assert loaded.flags == {"met_marta": "yes"}
    assert loaded.location_id == "delta-crossing"
    assert [n.npc_id for n in loaded.npcs] == ["the-sweeper"]
    back, _ = apply_changes(loaded, [{"kind": "move", "location_id": "medallion-inn"}])
    store.commit(sid, back)
    assert [(n.npc_id, n.disposition) for n in store.load(sid).npcs] == [("marta-quill", 1)]


def test_list_and_delete(store, sid):
    store.create_adventure(sid, "player-list-test", "Elowen", "mage")
    listed = [a for a in store.list_adventures("player-list-test") if a["session_id"] == sid]
    assert listed == [{"session_id": sid, "name": "Elowen", "archetype": "mage",
                       "location_id": "medallion-inn", "status": "active"}]
    store.delete_adventure(sid)
    assert store.load(sid) is None
```

- [ ] **Step 3: Run them and check they fail**

Run: `cd dm && uv run pytest tests/test_store.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'rpg.store'`.

- [ ] **Step 4: Implement**

`dm/rpg/store.py`:
```python
"""Where game state lives. GameStore is the contract, and InMemoryStore backs tests and dev without Lakebase."""

from pathlib import Path
from typing import Protocol

import yaml

from rpg.state import GameState, NpcCard, NpcPresence
from rpg.world import START_LOCATION_ID, Character, new_character


class GameStore(Protocol):
    def create_adventure(self, session_id: str, player_id: str, name: str, archetype: str) -> GameState: ...
    def load(self, session_id: str) -> GameState | None: ...
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
```

- [ ] **Step 5: Run the tests and check they pass**

Run: `cd dm && uv run pytest tests/test_store.py -q`
Expected: 7 memory-variant tests pass. The 6 postgres-variant tests (all the ones that use the `store` fixture) are skipped with "PGHOST not set".

- [ ] **Step 6: Commit**

```bash
git add content/npcs dm/rpg/store.py dm/tests/test_store.py
git commit -m "feat(rpg): add GameStore contract, in-memory store and NPC character cards

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 3: Lakebase project, schema and `PostgresStore`

**Files:**
- Create: `resources/lakebase.yml`, `scripts/lakebase_env.sh`, `dm/rpg/schema.sql`, `dm/agent/pgstore.py`
- Modify: `Makefile` (a `db` target; `deploy` calls it)
- Test: `dm/tests/test_pgstore.py`, plus `dm/tests/test_store.py`'s postgres variant, run live

**Interfaces:**
- Consumes: `rpg.store.GameStore` (the contract), `rpg.state`, `rpg.world.new_character`
- Produces:
  - `agent.pgstore.PostgresStore(connect: Callable[[], psycopg.Connection])` and `PostgresStore.from_env()`
  - `agent.pgstore.migrate(conn) -> None`
  - `agent.pgstore.lakebase_token() -> str`, cached and refreshed after `TOKEN_TTL_S = 45 * 60` seconds
  - `agent.pgstore.connect_from_env() -> psycopg.Connection`
  - CLI: `python -m agent.pgstore migrate <npcs_dir>`
  - `make db PROFILE=<p>`, and `scripts/lakebase_env.sh <profile> <project>`, which prints `export` lines for `PGHOST PGPORT PGDATABASE PGUSER LAKEBASE_ENDPOINT`

- [ ] **Step 1: Write the failing token-cache test**

`dm/tests/test_pgstore.py`:
```python
from types import SimpleNamespace

import agent.pgstore as pg


def test_token_is_cached_then_refreshed(monkeypatch):
    issued = []

    def generate_database_credential(endpoint):
        issued.append(endpoint)
        return SimpleNamespace(token=f"tok-{len(issued)}")

    clock = {"now": 1000.0}
    monkeypatch.setenv("LAKEBASE_ENDPOINT", "projects/p/branches/b/endpoints/e")
    monkeypatch.setattr(pg, "workspace_client",
                        lambda: SimpleNamespace(postgres=SimpleNamespace(generate_database_credential=generate_database_credential)))
    monkeypatch.setattr(pg.time, "time", lambda: clock["now"])
    monkeypatch.setattr(pg, "_token_cache", {"token": None, "at": 0.0})

    assert pg.lakebase_token() == "tok-1"
    clock["now"] += pg.TOKEN_TTL_S - 1
    assert pg.lakebase_token() == "tok-1"
    clock["now"] += 2
    assert pg.lakebase_token() == "tok-2"
    assert issued == ["projects/p/branches/b/endpoints/e"] * 2


def test_schema_sql_creates_all_tables():
    sql = pg.SCHEMA_SQL
    for table in ("characters", "inventory", "quest_flags", "adventures", "npc_cards", "npc_disposition"):
        assert f"rpg.{table}" in sql
```

- [ ] **Step 2: Run it and check it fails**

Run: `cd dm && uv run pytest tests/test_pgstore.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.pgstore'`.

- [ ] **Step 3: Write the schema and `PostgresStore`**

`dm/rpg/schema.sql`:
```sql
-- Databricks Adventure game state (spec §7). Idempotent: safe to run on every deploy.
CREATE SCHEMA IF NOT EXISTS rpg;

CREATE TABLE IF NOT EXISTS rpg.characters (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id   text NOT NULL,
    name        text NOT NULL,
    archetype   text NOT NULL,
    might       int  NOT NULL,
    wits        int  NOT NULL,
    charm       int  NOT NULL,
    hp          int  NOT NULL,
    max_hp      int  NOT NULL,
    xp          int  NOT NULL DEFAULT 0,
    gold        int  NOT NULL,
    location_id text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rpg.inventory (
    character_id uuid NOT NULL REFERENCES rpg.characters (id) ON DELETE CASCADE,
    item_id      text NOT NULL,
    qty          int  NOT NULL CHECK (qty > 0),
    PRIMARY KEY (character_id, item_id)
);

CREATE TABLE IF NOT EXISTS rpg.quest_flags (
    character_id uuid NOT NULL REFERENCES rpg.characters (id) ON DELETE CASCADE,
    flag         text NOT NULL,
    value        text NOT NULL,
    PRIMARY KEY (character_id, flag)
);

CREATE TABLE IF NOT EXISTS rpg.adventures (
    id           text PRIMARY KEY,  -- the invocation session_id
    character_id uuid NOT NULL REFERENCES rpg.characters (id) ON DELETE CASCADE,
    status       text NOT NULL DEFAULT 'active',
    started_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rpg.npc_cards (
    npc_id           text PRIMARY KEY,
    name             text NOT NULL,
    persona          text NOT NULL,
    speech_style     text NOT NULL,
    secrets          text NOT NULL,
    home_location_id text NOT NULL
);

CREATE TABLE IF NOT EXISTS rpg.npc_disposition (
    character_id uuid NOT NULL REFERENCES rpg.characters (id) ON DELETE CASCADE,
    npc_id       text NOT NULL REFERENCES rpg.npc_cards (npc_id),
    disposition  int  NOT NULL CHECK (disposition BETWEEN -3 AND 3),
    PRIMARY KEY (character_id, npc_id)
);

CREATE INDEX IF NOT EXISTS characters_player_idx ON rpg.characters (player_id);
```

`dm/agent/pgstore.py`:
```python
"""GameStore on Lakebase Postgres. Each method is one connection and one transaction.

Connection settings come from PGHOST/PGPORT/PGDATABASE/PGUSER/LAKEBASE_ENDPOINT, which is the same
contract Databricks Apps inject for a Lakebase resource. The password is a short-lived OAuth token.
"""

import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Callable

import psycopg
from databricks_agentkit import workspace_client

from rpg.state import GameState, NpcCard, NpcPresence
from rpg.store import load_npc_cards
from rpg.world import START_LOCATION_ID, Character, new_character

SCHEMA_SQL = (Path(__file__).resolve().parents[1] / "rpg" / "schema.sql").read_text()
TOKEN_TTL_S = 45 * 60  # tokens last 1 hour; refresh well before
_token_cache: dict = {"token": None, "at": 0.0}


def lakebase_token() -> str:
    now = time.time()
    if _token_cache["token"] is None or now - _token_cache["at"] >= TOKEN_TTL_S:
        cred = workspace_client().postgres.generate_database_credential(endpoint=os.environ["LAKEBASE_ENDPOINT"])
        _token_cache.update(token=cred.token, at=now)
    return _token_cache["token"]


def connect_from_env() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ["PGHOST"], port=int(os.getenv("PGPORT", "5432")), dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"], password=lakebase_token(), sslmode="require", connect_timeout=10,
    )


def migrate(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_SQL)


_CHAR_COLS = "c.id, c.name, c.archetype, c.might, c.wits, c.charm, c.hp, c.max_hp, c.xp, c.gold, c.location_id"


class PostgresStore:
    def __init__(self, connect: Callable[[], psycopg.Connection]):
        self._connect = connect

    @classmethod
    def from_env(cls) -> "PostgresStore":
        return cls(connect_from_env)

    def seed_npcs(self, cards: list[NpcCard]) -> None:
        with self._connect() as conn:
            for c in cards:
                conn.execute(
                    "INSERT INTO rpg.npc_cards (npc_id, name, persona, speech_style, secrets, home_location_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (npc_id) DO UPDATE SET name = EXCLUDED.name, "
                    "persona = EXCLUDED.persona, speech_style = EXCLUDED.speech_style, secrets = EXCLUDED.secrets, "
                    "home_location_id = EXCLUDED.home_location_id",
                    (c.npc_id, c.name, c.persona, c.speech_style, c.secrets, c.home_location_id),
                )

    def create_adventure(self, session_id, player_id, name, archetype):
        c = new_character(name, archetype)
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM rpg.adventures WHERE id = %s", (session_id,)).fetchone():
                raise ValueError(f"adventure already exists for session {session_id}")
            (cid,) = conn.execute(
                "INSERT INTO rpg.characters (player_id, name, archetype, might, wits, charm, hp, max_hp, xp, gold, "
                "location_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (player_id, c.name, c.archetype, c.might, c.wits, c.charm, c.hp, c.max_hp, c.xp, c.gold,
                 START_LOCATION_ID),
            ).fetchone()
            self._write_inventory(conn, cid, c.inventory)
            conn.execute("INSERT INTO rpg.adventures (id, character_id) VALUES (%s, %s)", (session_id, cid))
        return self.load(session_id)

    def load(self, session_id):
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT {_CHAR_COLS} FROM rpg.adventures a JOIN rpg.characters c ON c.id = a.character_id "
                "WHERE a.id = %s", (session_id,),
            ).fetchone()
            if row is None:
                return None
            cid, name, archetype, might, wits, charm, hp, max_hp, xp, gold, location_id = row
            inventory = [item for item, qty in conn.execute(
                "SELECT item_id, qty FROM rpg.inventory WHERE character_id = %s ORDER BY item_id", (cid,)
            ).fetchall() for _ in range(qty)]
            flags = dict(conn.execute("SELECT flag, value FROM rpg.quest_flags WHERE character_id = %s", (cid,)).fetchall())
            npcs = [
                NpcPresence(npc_id=r[0], name=r[1], persona=r[2], speech_style=r[3], secrets=r[4],
                            home_location_id=r[5], disposition=r[6])
                for r in conn.execute(
                    "SELECT n.npc_id, n.name, n.persona, n.speech_style, n.secrets, n.home_location_id, "
                    "COALESCE(d.disposition, 0) FROM rpg.npc_cards n LEFT JOIN rpg.npc_disposition d "
                    "ON d.npc_id = n.npc_id AND d.character_id = %s WHERE n.home_location_id = %s ORDER BY n.npc_id",
                    (cid, location_id),
                ).fetchall()
            ]
        character = Character(name=name, archetype=archetype, might=might, wits=wits, charm=charm, hp=hp,
                              max_hp=max_hp, xp=xp, gold=gold, inventory=inventory)
        return GameState(character=character, location_id=location_id, flags=flags, npcs=npcs)

    def commit(self, session_id, state):
        c = state.character
        with self._connect() as conn:
            found = conn.execute("SELECT character_id FROM rpg.adventures WHERE id = %s", (session_id,)).fetchone()
            if found is None:
                raise LookupError(f"no adventure for session {session_id}")
            (cid,) = found
            conn.execute("UPDATE rpg.characters SET hp = %s, xp = %s, gold = %s, location_id = %s WHERE id = %s",
                         (c.hp, c.xp, c.gold, state.location_id, cid))
            conn.execute("DELETE FROM rpg.inventory WHERE character_id = %s", (cid,))
            self._write_inventory(conn, cid, c.inventory)
            for flag, value in state.flags.items():
                conn.execute("INSERT INTO rpg.quest_flags (character_id, flag, value) VALUES (%s, %s, %s) "
                             "ON CONFLICT (character_id, flag) DO UPDATE SET value = EXCLUDED.value", (cid, flag, value))
            for npc in state.npcs:
                conn.execute("INSERT INTO rpg.npc_disposition (character_id, npc_id, disposition) VALUES (%s, %s, %s) "
                             "ON CONFLICT (character_id, npc_id) DO UPDATE SET disposition = EXCLUDED.disposition",
                             (cid, npc.npc_id, npc.disposition))
            conn.execute("UPDATE rpg.adventures SET updated_at = now() WHERE id = %s", (session_id,))

    def list_adventures(self, player_id):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT a.id, c.name, c.archetype, c.location_id, a.status FROM rpg.adventures a "
                "JOIN rpg.characters c ON c.id = a.character_id WHERE c.player_id = %s ORDER BY a.updated_at DESC",
                (player_id,),
            ).fetchall()
        return [dict(zip(("session_id", "name", "archetype", "location_id", "status"), r)) for r in rows]

    def delete_adventure(self, session_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM rpg.characters WHERE id = (SELECT character_id FROM rpg.adventures WHERE id = %s)",
                         (session_id,))

    @staticmethod
    def _write_inventory(conn, cid, inventory: list[str]) -> None:
        for item, qty in Counter(inventory).items():
            conn.execute("INSERT INTO rpg.inventory (character_id, item_id, qty) VALUES (%s, %s, %s)", (cid, item, qty))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or args[0] != "migrate":
        print("usage: python -m agent.pgstore migrate <npcs_dir>", file=sys.stderr)
        return 2
    with connect_from_env() as conn:
        migrate(conn)
    cards = load_npc_cards(args[1])
    PostgresStore.from_env().seed_npcs(cards)
    print(f"migrated schema rpg and seeded {len(cards)} NPC cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the unit tests**

Run: `cd dm && uv run pytest tests/test_pgstore.py -q`
Expected: 2 passed.

- [ ] **Step 5: Add Lakebase to the bundle, plus the env script and `make db`**

`resources/lakebase.yml`:
```yaml
resources:
  postgres_projects:
    game_db:
      project_id: databricks-adventure
      display_name: Databricks Adventure
```

`scripts/lakebase_env.sh`:
```bash
#!/usr/bin/env bash
# Print export lines for connecting to the game's Lakebase project as the current user.
# Usage: eval "$(scripts/lakebase_env.sh <profile> [project_id])"
set -euo pipefail
PROFILE="$1"; PROJECT="${2:-databricks-adventure}"
EP="projects/$PROJECT/branches/production/endpoints/primary"
HOST=$(databricks postgres get-endpoint "$EP" --profile "$PROFILE" -o json | jq -r '.status.hosts.host')
USER_NAME=$(databricks current-user me --profile "$PROFILE" -o json | jq -r '.userName')
echo "export PGHOST=$HOST PGPORT=5432 PGDATABASE=databricks_postgres PGUSER=$USER_NAME LAKEBASE_ENDPOINT=$EP"
```
Then `chmod +x scripts/lakebase_env.sh`.

In the `Makefile`:
1. Add `LAKEBASE_PROJECT ?= databricks-adventure` below `SCHEMA ?=`.
2. Add `db` to `.PHONY`.
3. In `deploy`, add `$(MAKE) db PROFILE=$(PROFILE)` right after the `$(BUNDLE) deploy` line.
4. Add the target:
```makefile
db:
	@test -n "$(PROFILE)" || (echo "Set PROFILE=<databricks-profile>" && exit 1)
	eval "$$(scripts/lakebase_env.sh $(PROFILE) $(LAKEBASE_PROJECT))" && cd dm && \
		DATABRICKS_CONFIG_PROFILE=$(PROFILE) uv run python -m agent.pgstore migrate ../content/npcs
```

- [ ] **Step 6: Deploy the project and migrate**

```bash
databricks bundle validate --profile brickbots --var catalog=serverless_stable_brickbots_catalog
databricks bundle deploy --profile brickbots --var catalog=serverless_stable_brickbots_catalog
databricks postgres list-endpoints projects/databricks-adventure/branches/production --profile brickbots -o json | jq -r '.[].name'
make db PROFILE=brickbots
```
Expected:
- Validation is OK, and it lists `postgres_projects.game_db`.
- The deploy creates the project. That can take a few minutes.
- The endpoint list includes `projects/databricks-adventure/branches/production/endpoints/primary`. If the branch or endpoint ids differ, change `EP=` in `scripts/lakebase_env.sh` to match, and record a ruling.
- `make db` prints `migrated schema rpg and seeded 2 NPC cards`.

If psycopg can't resolve the host on macOS (long hostnames), add `hostaddr=$(dig +short <host> | tail -1)` to the connect arguments via a `PGHOSTADDR` env var, and record a ruling.

- [ ] **Step 7: Run the contract suite against Lakebase**

```bash
eval "$(scripts/lakebase_env.sh brickbots)"
cd dm && DATABRICKS_CONFIG_PROFILE=brickbots uv run pytest tests/test_store.py -v
```
Expected: all 13 tests pass, with the 6 postgres variants now running instead of skipped. Then save the connection for dev:
```bash
cd .. && scripts/lakebase_env.sh brickbots | sed 's/^export //' | tr ' ' '\n' >> dm/.env
git check-ignore dm/.env
```

- [ ] **Step 8: Commit**

```bash
git add resources/lakebase.yml scripts/lakebase_env.sh Makefile dm/rpg/schema.sql dm/agent/pgstore.py dm/tests/test_pgstore.py
git commit -m "feat(state): Lakebase project in the bundle, rpg schema and PostgresStore

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 4: Staged state tools and combat tools

**Files:**
- Create: `dm/agent/tools/state_tools.py`
- Modify: `dm/agent/tools/dice.py`
- Test: `dm/tests/test_state_tools.py`

**Interfaces:**
- Consumes: `rpg.state` change models, `rpg.rules.resolve_attack`, `rpg.world.LOCATIONS`, `Character`
- Produces (the model-visible arguments are listed; `state` and `tool_call_id` are injected):
  - `update_character(hp_delta=0, gold_delta=0, xp_delta=0, items_add=None, items_remove=None, reason="")`. Limits: `|hp_delta| ≤ 50`, `|gold_delta| ≤ 1000`, `0 ≤ xp_delta ≤ 100`, at most 5 items per list, each item 40 characters at most.
  - `set_quest_flag(flag, value)`
  - `set_npc_disposition(npc_id, delta, reason)`, with `delta ∈ [-2, 2]` and `npc_id` among `state["npcs"]`
  - `move_to(location_id)`, where `location_id` must be one of the current location's exits
  - `resolve_attack(stat: "might"|"wits", target, target_defence, damage_die, damage_bonus)`, which returns a dict with no state change
  - `enemy_attack(attacker, attack_bonus (0..10), damage_die, damage_bonus)`, which stages `hp_delta = -damage` on a hit
  - Staging tools return `Command(update={"staged": [change_dict], "messages": [ToolMessage(json, name=<tool>, tool_call_id=...)]})`. The ToolMessage content is `{"staged": change}` (or `{"staged": change, **attack}` for `enemy_attack`). On a validation error they return `{"error": ...}`, with nothing staged.

- [ ] **Step 1: Write the failing tests**

`dm/tests/test_state_tools.py`:
```python
import json
import random

import agent.tools.dice as dice
import pytest
from agent.tools import all_tools
from agent.tools.dice import enemy_attack, resolve_attack
from agent.tools.state_tools import move_to, set_npc_disposition, set_quest_flag, update_character
from langgraph.types import Command
from rpg.world import new_character

STATE = {
    "character": new_character("Brannoc", "warrior").model_dump(),
    "location_id": "medallion-inn",
    "npcs": [{"npc_id": "marta-quill", "name": "Marta Quill", "persona": "p", "speech_style": "s",
              "secrets": "x", "home_location_id": "medallion-inn", "disposition": 0}],
}


class SeqRng(random.Random):
    def __init__(self, *v):
        super().__init__(0)
        self.v = list(v)

    def randint(self, a, b):
        return self.v.pop(0)


def call(tool, **args):
    out = tool.invoke({"name": tool.name, "args": {**args, "state": STATE}, "id": "c1", "type": "tool_call"})
    if isinstance(out, Command):
        msg = out.update["messages"][0]
        assert msg.name == tool.name and msg.tool_call_id == "c1"
        return json.loads(msg.content), out.update.get("staged", [])
    return json.loads(out.content) if hasattr(out, "content") else out, []


def test_tools_registered():
    names = {t.name for t in all_tools()}
    assert {"update_character", "set_quest_flag", "set_npc_disposition", "move_to",
            "resolve_attack", "enemy_attack"} <= names


def test_model_never_sees_injected_args():
    for t in (update_character, set_quest_flag, set_npc_disposition, move_to, resolve_attack, enemy_attack):
        props = set(t.tool_call_schema.model_json_schema()["properties"])
        assert not props & {"state", "tool_call_id", "modifier", "defence"}, t.name


def test_update_character_stages_change():
    content, staged = call(update_character, hp_delta=-3, items_add=["lantern"], reason="burnt")
    assert staged == [{"kind": "character", "hp_delta": -3, "xp_delta": 0, "gold_delta": 0,
                       "items_add": ["lantern"], "items_remove": []}]
    assert content == {"staged": staged[0]}


@pytest.mark.parametrize("args", [{"hp_delta": -51}, {"gold_delta": 5000}, {"xp_delta": -1},
                                  {"items_add": ["x"] * 6}, {"items_add": ["y" * 41]}])
def test_update_character_rejects_out_of_bounds(args):
    content, staged = call(update_character, **args)
    assert "error" in content and staged == []


def test_quest_flag_validates_slug():
    assert call(set_quest_flag, flag="met_marta", value="yes")[1] == [{"kind": "flag", "flag": "met_marta", "value": "yes"}]
    content, staged = call(set_quest_flag, flag="Met Marta!", value="yes")
    assert "error" in content and staged == []


def test_disposition_requires_present_npc_and_small_delta():
    assert call(set_npc_disposition, npc_id="marta-quill", delta=1, reason="helped")[1][0]["delta"] == 1
    content, staged = call(set_npc_disposition, npc_id="the-sweeper", delta=1, reason="x")
    assert "marta-quill" in content["error"] and staged == []
    assert call(set_npc_disposition, npc_id="marta-quill", delta=3, reason="x")[1] == []


def test_move_to_only_exits():
    assert call(move_to, location_id="delta-crossing")[1] == [{"kind": "move", "location_id": "delta-crossing"}]
    content, staged = call(move_to, location_id="unity-archive")
    assert "delta-crossing" in content["error"] and staged == []


def test_resolve_attack_uses_state_modifier(monkeypatch):
    monkeypatch.setattr(dice, "RNG", SeqRng(9, 4))
    out, staged = call(resolve_attack, stat="might", target="River wraith", target_defence=12, damage_die=6, damage_bonus=2)
    assert (out["modifier"], out["total"], out["hit"], out["damage"], out["target"]) == (3, 12, True, 6, "River wraith")
    assert staged == []


def test_enemy_attack_stages_damage_against_player_defence(monkeypatch):
    monkeypatch.setattr(dice, "RNG", SeqRng(12, 3))
    content, staged = call(enemy_attack, attacker="River wraith", attack_bonus=3, damage_die=6, damage_bonus=1)
    assert content["defence"] == 13 and content["hit"] is True and content["damage"] == 4
    assert staged[0]["hp_delta"] == -4


def test_enemy_attack_miss_stages_nothing(monkeypatch):
    monkeypatch.setattr(dice, "RNG", SeqRng(2))
    content, staged = call(enemy_attack, attacker="Swamp rat", attack_bonus=2, damage_die=4, damage_bonus=0)
    assert content["hit"] is False and staged == []


def test_enemy_attack_rejects_silly_bonus():
    content, staged = call(enemy_attack, attacker="Dragon", attack_bonus=50, damage_die=6, damage_bonus=0)
    assert "error" in content and staged == []
```

- [ ] **Step 2: Run them and check they fail**

Run: `cd dm && uv run pytest tests/test_state_tools.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.tools.state_tools'`.

- [ ] **Step 3: Implement the state tools**

`dm/agent/tools/state_tools.py`:
```python
"""Tools that stage changes to the saved game. Nothing is written until commit_state ends the turn."""

import json
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import ValidationError

from rpg.state import CharacterChange, DispositionChange, FlagChange, MoveChange
from rpg.world import LOCATIONS

State = Annotated[dict, InjectedState]
CallId = Annotated[str, InjectedToolCallId]


def reply(name: str, tool_call_id: str, content: dict, change: dict | None = None) -> Command:
    update: dict = {"messages": [ToolMessage(json.dumps(content), name=name, tool_call_id=tool_call_id)]}
    if change is not None:
        update["staged"] = [change]
    return Command(update=update)


def _stage(name: str, tool_call_id: str, model_cls, **fields) -> Command:
    try:
        change = model_cls(**fields).model_dump()
    except ValidationError as e:
        return reply(name, tool_call_id, {"error": e.errors()[0]["msg"]})
    return reply(name, tool_call_id, {"staged": change}, change)


@tool
def update_character(
    state: State, tool_call_id: CallId, hp_delta: int = 0, gold_delta: int = 0, xp_delta: int = 0,
    items_add: list[str] | None = None, items_remove: list[str] | None = None, reason: str = "",
) -> Command:
    """Change the player character's HP, gold, XP or inventory: healing, non-combat harm, buying,
    paying, finding, losing or using up items, or rewards. Changes apply at the end of the turn."""
    items_add, items_remove = items_add or [], items_remove or []
    problems = [
        abs(hp_delta) > 50 and "hp_delta must be between -50 and 50",
        abs(gold_delta) > 1000 and "gold_delta must be between -1000 and 1000",
        not 0 <= xp_delta <= 100 and "xp_delta must be between 0 and 100",
        (len(items_add) > 5 or len(items_remove) > 5) and "at most 5 items at a time",
        any(len(i) > 40 or not i.strip() for i in [*items_add, *items_remove]) and "item names must be 1-40 characters",
    ]
    if errors := [p for p in problems if p]:
        return reply("update_character", tool_call_id, {"error": "; ".join(errors)})
    return _stage("update_character", tool_call_id, CharacterChange, hp_delta=hp_delta, gold_delta=gold_delta,
                  xp_delta=xp_delta, items_add=items_add, items_remove=items_remove)


@tool
def set_quest_flag(flag: str, value: str, state: State, tool_call_id: CallId) -> Command:
    """Record story progress as a snake_case flag, e.g. met_the_sweeper = yes or archive_door = forced."""
    return _stage("set_quest_flag", tool_call_id, FlagChange, flag=flag, value=value)


@tool
def set_npc_disposition(npc_id: str, delta: int, reason: str, state: State, tool_call_id: CallId) -> Command:
    """Shift how an NPC who is present feels about the player: +1 or +2 when helped or charmed,
    -1 or -2 when insulted or cheated."""
    present = [n["npc_id"] for n in state.get("npcs", [])]
    if npc_id not in present:
        return reply("set_npc_disposition", tool_call_id, {"error": f"{npc_id} is not here; present: {present}"})
    if not -2 <= delta <= 2:
        return reply("set_npc_disposition", tool_call_id, {"error": "delta must be between -2 and 2"})
    return _stage("set_npc_disposition", tool_call_id, DispositionChange, npc_id=npc_id, delta=delta)


@tool
def move_to(location_id: str, state: State, tool_call_id: CallId) -> Command:
    """Move the player to a neighbouring location when they travel there. Only the current location's exits are reachable."""
    here = LOCATIONS[state["location_id"]]
    if location_id not in here.exits:
        return reply("move_to", tool_call_id, {"error": f"cannot reach {location_id}; exits: {list(here.exits)}"})
    return _stage("move_to", tool_call_id, MoveChange, location_id=location_id)
```

- [ ] **Step 4: Add the combat tools to `dice.py`**

In `dm/agent/tools/dice.py`, change the imports to:
```python
import random
from typing import Annotated, Literal

from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from agent.tools.state_tools import reply
from rpg import rules
from rpg.state import CharacterChange
from rpg.world import Character
```
Then append:
```python
@tool
def resolve_attack(
    stat: Literal["might", "wits"], target: str, target_defence: int, damage_die: int, damage_bonus: int,
    state: Annotated[dict, InjectedState],
) -> dict:
    """The player attacks a creature. Use might for weapons and wits for spells. Take the target's
    defence from the bestiary, and the player's weapon damage from the rules (longsword or ember
    wand: die 6, bonus 2; rapier: die 6, bonus 1). Track the creature's wounds in your narration."""
    character = Character.model_validate(state["character"])
    try:
        result = rules.resolve_attack(character.modifier(rules.Stat(stat)), target_defence, damage_die, damage_bonus, RNG)
    except ValueError as e:
        return {"error": str(e)}
    return {**result.to_dict(), "target": target}


@tool
def enemy_attack(
    attacker: str, attack_bonus: int, damage_die: int, damage_bonus: int,
    state: Annotated[dict, InjectedState], tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """A creature attacks the player. Use its attack bonus and damage from the bestiary. The
    player's defence and any damage to their HP are applied automatically."""
    character = Character.model_validate(state["character"])
    if not 0 <= attack_bonus <= 10:
        return reply("enemy_attack", tool_call_id, {"error": "attack_bonus must be between 0 and 10"})
    try:
        result = rules.resolve_attack(attack_bonus, character.defence, damage_die, damage_bonus, RNG)
    except ValueError as e:
        return reply("enemy_attack", tool_call_id, {"error": str(e)})
    content = {**result.to_dict(), "attacker": attacker, "target": character.name}
    if not result.hit:
        return reply("enemy_attack", tool_call_id, content)
    change = CharacterChange(hp_delta=-result.damage).model_dump()
    return reply("enemy_attack", tool_call_id, {**content, "staged": change}, change)
```

- [ ] **Step 5: Run the tests**

Run: `cd dm && uv run pytest -q`
Expected: everything passes, including 18 new tests in `test_state_tools.py`.

- [ ] **Step 6: Commit**

```bash
git add dm/agent/tools/state_tools.py dm/agent/tools/dice.py dm/tests/test_state_tools.py
git commit -m "feat(dm): add staged state tools and combat tools

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 5: Store-backed graph with `commit_state`

**Files:**
- Modify: `dm/agent/dm_graph.py`, `dm/agent/prompts.py`, `dm/tests/test_dm_graph.py`

**Interfaces:**
- Consumes: `GameStore`, `rpg.state.apply_changes`, `GameState`, the Task 4 tools, and `config["configurable"]["thread_id"]` as the session id
- Produces:
  - `build_dm_graph(llm, tools, checkpointer=None, *, store: GameStore)` (the store is required)
  - Node names: `load_state`, `dm_reason`, `tools`, `commit_state`, `compose`
  - New `DMState` keys: `flags: dict`, `npcs: list[dict]`, `staged` (reducer: `None` resets, a list appends), `state_summaries: list[str]`, `commit_failed: bool`
  - `load_state` raises `LookupError` if the session has no adventure
  - `COMMIT_FAILED_NARRATION: str`
  - `turn_events` adds `attack` events for `resolve_attack` and `enemy_attack`
  - `compose` appends one `TurnEvent(type="state", summary="; ".join(summaries), detail={"changes": staged})` when anything committed
  - `prompts.render_dm_system(game: GameState) -> str`, which includes the character sheet with defence, the location and named exits, flags, and NPC cards with disposition

- [ ] **Step 1: Point the existing graph tests at a store**

In `dm/tests/test_dm_graph.py`:
1. Add these imports:
```python
from pathlib import Path

from rpg.store import InMemoryStore, load_npc_cards
```
2. Replace the `make` function with:
```python
NPCS = Path(__file__).resolve().parents[2] / "content" / "npcs"


def new_store(sid="t1"):
    s = InMemoryStore(load_npc_cards(NPCS))
    s.create_adventure(sid, "player-1", "Brannoc", "warrior")
    return s


def make(model, tools=None, store=None):
    return build_dm_graph(model, tools or [roll_check], checkpointer=InMemorySaver(),
                          store=store if store is not None else new_store())
```
3. In `test_lore_tool_result_becomes_lore_event` and `test_failed_lore_lookup_still_completes_turn`, replace `graph = build_dm_graph(model, [roll_check, search_lore], checkpointer=InMemorySaver())` with `graph = make(model, [roll_check, search_lore])`.

- [ ] **Step 2: Write the new failing graph tests**

Append to `dm/tests/test_dm_graph.py`:
```python
from agent.dm_graph import COMMIT_FAILED_NARRATION
from agent.tools.dice import enemy_attack
from agent.tools.state_tools import move_to, update_character

STATE_TOOLS = [roll_check, update_character, move_to, enemy_attack]


def tc(name, idx=0, **args):
    return {"name": name, "args": args, "id": f"{name}-{idx}", "type": "tool_call"}


def test_staged_changes_commit_and_emit_state_event():
    store = new_store()
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[
            tc("update_character", hp_delta=-4, items_add=["lantern"]),
            tc("move_to", location_id="delta-crossing"),
        ]), AIMessage(content="draft")],
        structured=[PROSE],
    )
    turn = run(make(model, STATE_TOOLS, store), "I grab a lantern and head for the river.")["turn"]
    assert turn["location_id"] == "delta-crossing"
    state_event = turn["events"][-1]
    assert state_event["type"] == "state"
    assert "HP 18 → 14" in state_event["summary"] and "moved to The Delta Crossing" in state_event["summary"]
    saved = store.load("t1")
    assert saved.character.hp == 14 and "lantern" in saved.character.inventory
    assert [n.npc_id for n in saved.npcs] == ["the-sweeper"]


def test_no_staged_changes_means_no_state_event_and_no_commit():
    class CountingStore(InMemoryStore):
        commits = 0

        def commit(self, sid, state):
            CountingStore.commits += 1
            super().commit(sid, state)

    store = CountingStore(load_npc_cards(NPCS))
    store.create_adventure("t1", "p", "Brannoc", "warrior")
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    turn = run(make(model, STATE_TOOLS, store), "I look around.")["turn"]
    assert turn["events"] == [] and CountingStore.commits == 0


def test_enemy_attack_damage_is_committed(monkeypatch):
    class SeqRng(random.Random):
        def __init__(self, *v):
            super().__init__(0)
            self.v = list(v)

        def randint(self, a, b):
            return self.v.pop(0)

    monkeypatch.setattr(dice, "RNG", SeqRng(12, 3))
    store = new_store()
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[tc("enemy_attack", attacker="River wraith", attack_bonus=3,
                                                     damage_die=6, damage_bonus=1)]), AIMessage(content="d")],
        structured=[PROSE],
    )
    turn = run(make(model, STATE_TOOLS, store), "I wade in.")["turn"]
    assert [e["type"] for e in turn["events"]] == ["attack", "state"]
    assert store.load("t1").character.hp == 14


def test_commit_failure_keeps_state_and_cleans_history():
    class BrokenStore(InMemoryStore):
        def commit(self, sid, state):
            raise ConnectionError("lakebase unreachable")

    store = BrokenStore(load_npc_cards(NPCS))
    store.create_adventure("t1", "p", "Brannoc", "warrior")
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[tc("update_character", gold_delta=-2)]), AIMessage(content="d"),
                 AIMessage(content="ok")],
        structured=[PROSE],
    )
    graph = make(model, STATE_TOOLS, store)
    turn = run(graph, "I pay the ferryman.")["turn"]
    assert turn["narration"] == COMMIT_FAILED_NARRATION
    assert store.load("t1").character.gold == 12
    run(graph, "I try again.")
    retry_input = model.reason_calls[-1]
    assert not any(isinstance(m, ToolMessage) for m in retry_input)


def test_turn_without_adventure_raises():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    graph = make(model, store=InMemoryStore())
    with pytest.raises(LookupError):
        run(graph, "Hello")


def test_system_prompt_includes_npc_card_and_exits():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    run(make(model), "Hello")
    system = model.reason_calls[0][0].content
    assert "Marta Quill" in system and "disposition +0" in system
    assert "The Delta Crossing (delta-crossing)" in system
    assert "Defence 13" in system
```

- [ ] **Step 3: Run them and check they fail**

Run: `cd dm && uv run pytest tests/test_dm_graph.py -q`
Expected: the new tests and the updated `make()` tests fail with `TypeError: build_dm_graph() got an unexpected keyword argument 'store'` and `ImportError: cannot import name 'COMMIT_FAILED_NARRATION'`.

- [ ] **Step 4: Update the prompt**

In `dm/agent/prompts.py`:
1. Change the import to `from rpg.state import GameState` and `from rpg.world import LOCATIONS`.
2. In `DM_SYSTEM`, replace everything from `The player character:` to the end of the string with:
```
- Use update_character for any change to HP, gold, XP or items; move_to when the player travels; \
set_quest_flag to record story progress; set_npc_disposition when the player helps or offends \
someone present. Use resolve_attack when the player attacks and enemy_attack when something \
attacks the player. Never just say HP or gold changed without the tool.

The player character:
{character}

Current location: {location_name}
{location_description}
Exits: {exits}

Quest flags: {flags}

People here:
{npcs}
"""
```
3. Replace `render_dm_system` with:
```python
def render_dm_system(game: GameState) -> str:
    c = game.character
    sheet = (
        f"{c.name}, {c.archetype.title()}. HP {c.hp}/{c.max_hp}. Defence {c.defence}. "
        f"Might {c.might:+d}, Wits {c.wits:+d}, Charm {c.charm:+d}. Gold {c.gold}. XP {c.xp}. "
        f"Carrying: {', '.join(c.inventory) or 'nothing'}."
    )
    here = LOCATIONS[game.location_id]
    npcs = "\n".join(
        f"- {n.name} ({n.npc_id}), disposition {n.disposition:+d}. {n.persona} Speaks: {n.speech_style} "
        f"Secret (reveal only if earned): {n.secrets}"
        for n in game.npcs
    ) or "- nobody of note"
    return DM_SYSTEM.format(
        character=sheet,
        location_name=here.name,
        location_description=here.description,
        exits=", ".join(f"{LOCATIONS[e].name} ({e})" for e in here.exits) or "none",
        flags=", ".join(f"{k}={v}" for k, v in game.flags.items()) or "none yet",
        npcs=npcs,
    )
```

- [ ] **Step 5: Update the graph**

In `dm/agent/dm_graph.py`:
1. Imports: add `from langchain_core.runnables import RunnableConfig`, `from rpg.state import GameState, apply_changes`, `from rpg.store import GameStore`. Delete the `from rpg.world import ...` line, because nothing in the new graph uses it. Run `uvx ruff check agent --select F` to confirm there are no unused or missing names.
2. Below `FALLBACK_CHOICES`, add:
```python
COMMIT_FAILED_NARRATION = (
    "The world shimmers and slips, like a page turned too quickly. Nothing you just did seems "
    "to have stuck. What do you do?"
)


def _stage(left: list | None, right: list | None) -> list:
    """Reducer for staged changes: None resets (start of turn), a list appends."""
    return [] if right is None else [*(left or []), *right]
```
3. Replace the `DMState` class with:
```python
class DMState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    character: dict
    location_id: str
    flags: dict
    npcs: list[dict]
    staged: Annotated[list[dict], _stage]
    state_summaries: list[str]
    commit_failed: bool
    turn: dict | None
    reason_failed: bool


def _game(state: DMState) -> GameState:
    return GameState(character=state["character"], location_id=state["location_id"],
                     flags=state.get("flags") or {}, npcs=state.get("npcs") or [])


def _game_update(game: GameState) -> dict:
    return {"character": game.character.model_dump(), "location_id": game.location_id,
            "flags": dict(game.flags), "npcs": [n.model_dump() for n in game.npcs]}
```
4. Add the attack event builder next to `_lore_event`, and register both combat tools:
```python
def _attack_event(r: dict) -> TurnEvent:
    who = f"{r['attacker']} attacks {r['target']}" if "attacker" in r else f"Attack on {r['target']}"
    outcome = f"hit for {r['damage']}" if r["hit"] else "miss"
    summary = f"{who}: {r['roll']} {r['modifier']:+d} = {r['total']} vs defence {r['defence']}, {outcome}"
    return TurnEvent(type="attack", summary=summary, detail=r)


_EVENT_BUILDERS = {"roll_check": _roll_event, "search_lore": _lore_event,
                   "resolve_attack": _attack_event, "enemy_attack": _attack_event}
```
5. Replace `build_dm_graph` (the whole function) with:
```python
def build_dm_graph(llm: Any, tools: list[BaseTool], checkpointer: Any = None, *, store: GameStore):
    reasoner = llm.bind_tools(tools)

    def _sid(config: RunnableConfig) -> str:
        return config["configurable"]["thread_id"]

    def load_state(state: DMState, config: RunnableConfig) -> dict:
        game = store.load(_sid(config))
        if game is None:
            raise LookupError(f"no adventure for session {_sid(config)}")
        update = {**_game_update(game), "staged": None, "state_summaries": [], "commit_failed": False}
        messages = state.get("messages") or []
        if not messages or not isinstance(messages[-1], HumanMessage):
            update["messages"] = [HumanMessage(OPENING_CUE)]
        return update

    def dm_reason(state: DMState) -> dict:
        system = SystemMessage(render_dm_system(_game(state)))
        try:
            return {"messages": [reasoner.invoke([system, *_sendable(state["messages"])])]}
        except Exception:  # noqa: BLE001 - the world never breaks character; compose falls back
            logger.warning("dm_reason model call failed", exc_info=True)
            return {"reason_failed": True}

    def route(state: DMState) -> str:
        last = state["messages"][-1]
        calls = getattr(last, "tool_calls", None) or []
        if calls and _tool_calls_used(state["messages"]) + len(calls) <= MAX_TOOL_CALLS_PER_TURN:
            return "tools"
        return "commit_state"

    def commit_state(state: DMState, config: RunnableConfig) -> dict:
        staged = state.get("staged") or []
        if not staged:
            return {}
        try:
            new, summaries = apply_changes(_game(state), staged)
            store.commit(_sid(config), new)
            game = store.load(_sid(config))
        except Exception:  # noqa: BLE001 - rolled back by the store; the turn reports failure in-world
            logger.warning("commit_state failed", exc_info=True)
            return {"commit_failed": True}
        return {**_game_update(game), "state_summaries": summaries}

    def compose(state: DMState) -> dict:
        messages = state["messages"]
        previous = (state.get("turn") or {}).get("choices")
        events = turn_events(messages)
        if state.get("commit_failed"):
            turn = fallback_turn(state["location_id"], [], previous)
            turn.narration = COMMIT_FAILED_NARRATION
            removals = [RemoveMessage(id=m.id) for m in _current_turn(messages)
                        if not isinstance(m, HumanMessage)]
        else:
            if state.get("state_summaries"):
                events.append(TurnEvent(type="state", summary="; ".join(state["state_summaries"]),
                                        detail={"changes": state.get("staged") or []}))
            if state.get("reason_failed"):
                turn = fallback_turn(state["location_id"], events, previous)
            else:
                turn = compose_turn(llm, messages, state["location_id"], events, previous)
            removals = [RemoveMessage(id=messages[-1].id)] if isinstance(messages[-1], AIMessage) else []
        text = turn.narration + "\n\n" + "\n".join(f"- {c}" for c in turn.choices)
        return {"turn": turn.model_dump(), "messages": [*removals, AIMessage(content=text)],
                "reason_failed": False, "commit_failed": False}

    builder = StateGraph(DMState)
    builder.add_node("load_state", load_state)
    builder.add_node("dm_reason", dm_reason)
    builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    builder.add_node("commit_state", commit_state)
    builder.add_node("compose", compose)
    builder.add_edge(START, "load_state")
    builder.add_edge("load_state", "dm_reason")
    builder.add_conditional_edges("dm_reason", route, {"tools": "tools", "commit_state": "commit_state"})
    builder.add_edge("tools", "dm_reason")
    builder.add_edge("commit_state", "compose")
    builder.add_edge("compose", END)
    return builder.compile(checkpointer=checkpointer)
```

- [ ] **Step 6: Run the tests**

Run: `cd dm && uv run pytest -q`
Expected: everything passes, including the 6 new graph tests. `test_agent.py` may fail where `create_agent_graph` doesn't pass a store yet; that's fixed in Task 6. If so, run `uv run pytest -q --deselect tests/test_agent.py` for this task's gate, and record it in the ledger.

- [ ] **Step 7: Commit**

```bash
git add dm/agent/dm_graph.py dm/agent/prompts.py dm/tests/test_dm_graph.py
git commit -m "feat(dm): load and commit game state per turn with state and attack events

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 6: `new_game` in the adapter, and store wiring

**Files:**
- Modify: `dm/agent/agent.py`, `dm/runtime/adapter.py`, `dm/tests/test_agent.py`

**Interfaces:**
- Consumes: `build_dm_graph(..., store=)`, `PostgresStore.from_env`, `InMemoryStore`, `load_npc_cards`, `ARCHETYPES`
- Produces:
  - `agent.agent.game_store() -> GameStore`, a process-wide singleton. It's a `PostgresStore` if `PGHOST` is set, otherwise an `InMemoryStore` seeded from the repo's `content/npcs`.
  - Invocation input gains an optional `new_game: {"name": str (1–40 chars), "archetype": "warrior"|"mage"|"bard"}`
  - The adapter rule: with `new_game`, it creates the adventure for `session_id` and `actor` **if none exists** (so replays are idempotent). Without it, the session must already have an adventure, otherwise it raises `ValueError("no adventure for this session: send new_game first")`.

- [ ] **Step 1: Write the failing tests**

Append to `dm/tests/test_agent.py`:
```python
@pytest.fixture
def mem_store(monkeypatch):
    from pathlib import Path

    import agent.agent as agent_module
    from rpg.store import InMemoryStore, load_npc_cards

    store = InMemoryStore(load_npc_cards(Path(__file__).resolve().parents[2] / "content" / "npcs"))
    monkeypatch.setattr(agent_module, "game_store", lambda: store)
    return store


@pytest.fixture
def capture_run(monkeypatch):
    import runtime.adapter as adapter

    calls = []

    async def fake_run_agent(agent_input, **kwargs):
        calls.append(kwargs)
        if False:
            yield None

    monkeypatch.setattr(adapter, "run_agent", fake_run_agent)
    return calls


def ctx(session="s-new"):
    return SimpleNamespace(invocation_id="inv-1", session_id=session, emit=AsyncMock())


@pytest.mark.asyncio
async def test_new_game_creates_adventure(mem_store, capture_run):
    from runtime.adapter import invoke

    await invoke({"messages": [], "new_game": {"name": "Elowen", "archetype": "mage"}, "actor": "p1"}, ctx())
    game = mem_store.load("s-new")
    assert game.character.name == "Elowen" and game.character.archetype == "mage"
    assert mem_store.list_adventures("p1")[0]["session_id"] == "s-new"
    assert capture_run


@pytest.mark.asyncio
async def test_new_game_replay_is_idempotent(mem_store, capture_run):
    from runtime.adapter import invoke

    payload = {"messages": [], "new_game": {"name": "Elowen", "archetype": "mage"}}
    await invoke(payload, ctx())
    await invoke(payload, ctx())
    assert len(capture_run) == 2
    assert mem_store.load("s-new").character.name == "Elowen"


@pytest.mark.asyncio
async def test_turn_without_adventure_is_rejected(mem_store, capture_run):
    from runtime.adapter import invoke

    with pytest.raises(ValueError, match="new_game"):
        await invoke({"messages": [{"role": "user", "content": "hi"}]}, ctx("s-none"))
    assert capture_run == []


@pytest.mark.parametrize("ng", [
    {"name": "", "archetype": "mage"}, {"name": "x" * 41, "archetype": "mage"},
    {"name": "Bob", "archetype": "paladin"}, "Bob", {"archetype": "bard"},
])
@pytest.mark.asyncio
async def test_bad_new_game_rejected(mem_store, capture_run, ng):
    from runtime.adapter import invoke

    with pytest.raises(ValueError):
        await invoke({"messages": [], "new_game": ng}, ctx())
    assert mem_store.load("s-new") is None


def test_game_store_falls_back_to_memory_without_pghost(monkeypatch):
    import agent.agent as agent_module
    from rpg.store import InMemoryStore

    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.setattr(agent_module, "_store", None)
    store = agent_module.game_store()
    assert isinstance(store, InMemoryStore) and store is agent_module.game_store()
```
Then make the existing adapter tests create their adventures. In `test_invoke_returns_turn`, add the `mem_store` fixture parameter and put `mem_store.create_adventure("s-1", "p", "Brannoc", "warrior")` as the first line. In `test_adapter_calls_same_run_agent_for_invoke_and_recovery`, add the `mem_store` parameter and put `mem_store.create_adventure("runtime-session", "p", "Brannoc", "warrior")` as the first line.

- [ ] **Step 2: Run them and check they fail**

Run: `cd dm && uv run pytest tests/test_agent.py -q`
Expected: the new tests fail. `game_store` doesn't exist yet (an `AttributeError` from monkeypatch), and the new-game assertions fail.

- [ ] **Step 3: Wire the store into `agent.py`**

In `dm/agent/agent.py`:
1. Add imports: `from pathlib import Path`, `from rpg.store import GameStore, InMemoryStore, load_npc_cards`.
2. After the `MODEL = ...` line, add:
```python
NPC_DIR = Path(__file__).resolve().parents[2] / "content" / "npcs"
_store: GameStore | None = None


def game_store() -> GameStore:
    """Lakebase when PGHOST is configured, otherwise an in-memory store (dev without a database)."""
    global _store
    if _store is None:
        if os.getenv("PGHOST"):
            from agent.pgstore import PostgresStore

            _store = PostgresStore.from_env()
        else:
            _store = InMemoryStore(load_npc_cards(NPC_DIR) if NPC_DIR.is_dir() else [])
    return _store
```
3. In `create_agent_graph`, change the return to `return build_dm_graph(llm, tools, checkpointer=checkpointer(), store=game_store())`.

- [ ] **Step 4: Handle `new_game` in the adapter**

In `dm/runtime/adapter.py`, add below `_agent_input`:
```python
def _new_game(payload: dict[str, Any]) -> tuple[str, str] | None:
    ng = payload.get("new_game")
    if ng is None:
        return None
    from rpg.world import ARCHETYPES

    name = ng.get("name") if isinstance(ng, dict) else None
    archetype = ng.get("archetype") if isinstance(ng, dict) else None
    if not (isinstance(name, str) and 1 <= len(name.strip()) <= 40):
        raise ValueError("new_game.name must be 1-40 characters")
    if archetype not in ARCHETYPES:
        raise ValueError(f"new_game.archetype must be one of {sorted(ARCHETYPES)}")
    return name.strip(), archetype


def _ensure_adventure(payload: dict[str, Any], session_id: str, actor: str) -> None:
    """Create the adventure on new_game (idempotent for replays); otherwise require one to exist."""
    store = agent_module.game_store()
    new_game = _new_game(payload)
    if store.load(session_id) is not None:
        return
    if new_game is None:
        raise ValueError("no adventure for this session: send new_game first")
    store.create_adventure(session_id, actor, *new_game)
```
In `_invoke_agent`, right after `actor = auth.namespace("actor", actor)` (and its `if` line), add:
```python
    _ensure_adventure(payload, session_id, actor)
```

- [ ] **Step 5: Run the tests**

Run: `cd dm && uv run pytest -q`
Expected: everything passes, including 9 new adapter tests (5 named plus 4 extra parametrised cases).

- [ ] **Step 6: Commit**

```bash
git add dm/agent/agent.py dm/runtime/adapter.py dm/tests/test_agent.py
git commit -m "feat(dm): start adventures with new_game and wire the game store

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 7: Live playthrough on Lakebase, docs and spec deltas

**Files:**
- Modify: `dm/scripts/smoke_turns.sh`, `dm/README.md`, `dm/.env.example`, `README.md`, `docs/superpowers/specs/2026-10-16-databricks-rpg-design.md`
- Create: `docs/design/screenshots/2026-10-16-m3a-state-trace.png`

- [ ] **Step 1: Update the smoke script**

Replace the body of `dm/scripts/smoke_turns.sh` from the `turn() {` line to the end with:
```bash
turn() {
  local content="$1" extra="${2:-}" body out
  [ -n "$extra" ] || extra='{}'
  body=$(jq -n --arg id "$(uuidgen)" --arg s "$SESSION" --arg c "$content" --argjson extra "$extra" \
    '{id:$id, session_id:$s, input:({messages:(if $c == "" then [] else [{role:"user", content:$c}] end), actor:"smoke-player"} + $extra)}')
  out=$(curl -sS --fail "$BASE/api/invocations" -H 'Content-Type: application/json' -d "$body")
  echo "$out" | jq -e '.output.turn.narration | length > 0' >/dev/null || { echo "FAIL: no narration"; echo "$out"; exit 1; }
  echo "$out" | jq -e '.output.turn.choices | length >= 2' >/dev/null || { echo "FAIL: <2 choices"; echo "$out"; exit 1; }
  echo "--- turn: ${content:-<new game>}"
  echo "$out" | jq -r '.output.turn.narration, (.output.turn.choices[] | "  > " + .),
    "  📍 " + .output.turn.location_id,
    (.output.turn.events[] | ({"roll":"🎲","lore":"📚","attack":"⚔️ ","state":"💾"}[.type] // "•") + " " + .summary)'
}

turn "" '{"new_game":{"name":"Brannoc","archetype":"warrior"}}'
turn "I try to charm Marta into telling me why the Archive is sealed."
turn "I buy a lantern from Marta for two gold."
turn "I head out of the inn and down to the Delta Crossing."
turn "I pay the Sweeper his two gold for the crossing."
echo "SMOKE OK (session $SESSION)"
```

- [ ] **Step 2: Play it live on Lakebase**

`dm/.env` already holds the `PG*`/`LAKEBASE_ENDPOINT` lines from Task 3. Remove any stale `dm/app.agentbricksdev.yaml` (it's gitignored), then from `dm/` start `agentbricks -p brickbots dev` in the background. Once it's listening, run `./scripts/smoke_turns.sh`.
Expected:
- Five turns, ending `SMOKE OK`.
- The lantern turn shows `💾 ... Gold 12 → 10; +lantern` (wording may vary, but gold and the lantern are there).
- The travel turn shows `📍 delta-crossing` and a `💾 ... moved to The Delta Crossing` event.
- The ferry turn shows a gold decrease. Its narration may mention the Sweeper, whose card loads at the Delta Crossing.

If the model skips a tool (for example, narrates paying without `update_character`), re-run once. If it still skips it, record it in the ledger as an M6 `tool_selection` eval finding.

- [ ] **Step 3: Check the save in Lakebase**

```bash
cd dm && set -a && . ./.env && set +a && uv run python -c "
from agent.pgstore import PostgresStore
for a in PostgresStore.from_env().list_adventures('smoke-player')[:1]:
    g = PostgresStore.from_env().load(a['session_id'])
    print(a['session_id'], g.location_id, g.character.hp, g.character.gold, sorted(g.character.inventory), g.flags)
"
```
Expected: the latest smoke session at `delta-crossing`, with gold reduced from 12, and `lantern` in the inventory.

- [ ] **Step 4: Screenshot the state trace**

Open the local MLflow URL that `agentbricks dev` printed. Find the travel turn's trace, and save a screenshot showing the `tools → move_to` and `commit_state` spans as `docs/design/screenshots/2026-10-16-m3a-state-trace.png`. Stop the server with `pkill -INT -f "agentbricks -p brickbots dev"`.

- [ ] **Step 5: Docs and spec deltas**

- `dm/.env.example`: append
```
# --- Game state (M3a): Lakebase connection. Generate with ../scripts/lakebase_env.sh <profile> ---
# Leave unset to use an in-memory store (state lost on restart).
# PGHOST=  PGPORT=5432  PGDATABASE=databricks_postgres  PGUSER=<you>  LAKEBASE_ENDPOINT=projects/databricks-adventure/branches/production/endpoints/primary
```
- `dm/README.md`: under the lore paragraph, add: `Game state lives in Lakebase when PG* variables are set (see .env.example), otherwise in memory. Start every session with "new_game": {"name": ..., "archetype": "warrior"|"mage"|"bard"} in the invocation input.`
- Root `README.md` deploy section: change the second sentence to start `This renders the lorebooks to PDF, deploys the bundle (schema, volume, AI Search endpoint, ingest job and the Lakebase game database), migrates the game schema, uploads the lore...`.
- Spec:
  - §15: replace item 3 with `3. **State (M3a).** Lakebase game tables, staged tools plus commit_state, new_game, NPC cards and combat. **Sessions and memory (M3b).** Managed session and memory stores, the memory pipeline and the first Agent Runtime deploy.`
  - §7: replace the `adventures(...)` line with `adventures(id = session_id, character_id, status, started_at, updated_at)`.
  - §5 combat bullet: append ` Player defence is 10 + max(Might, Wits). Enemy HP is tracked in narration only in v1.`
  - §4.3 tools table: add a row `| enemy_attack(attacker, attack_bonus, damage_die, damage_bonus) | Creature attacks the player against the player's defence; damage is staged automatically | Agent-side local tool |`.

- [ ] **Step 6: Commit**

```bash
git add dm/scripts/smoke_turns.sh dm/README.md dm/.env.example README.md docs/superpowers/specs docs/design/screenshots/2026-10-16-m3a-state-trace.png
git commit -m "feat(dm): live Lakebase playthrough smoke test, state trace screenshot and docs

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

## Done when

- `make test` passes. The Lakebase contract tests pass when `PG*` is set.
- `make deploy PROFILE=brickbots CATALOG=serverless_stable_brickbots_catalog` creates or updates the Lakebase project and migrates `rpg`.
- A live five-turn smoke on Lakebase shows 💾 events, a location change, and a matching save in `rpg.*`.
- Open for M3b: managed session and memory stores, the dreaming pipeline, the first `agentbricks deploy`, service principal grants (Lakebase schema `rpg`, AI Search index), and workspace tracing.
