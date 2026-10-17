# Milestone 7a: The Adventure (Story, Gates and Endings) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn sandbox mode into the full adventure from the story bible. That means:
- 8 locations, with **flag-gated exits** that `move_to` enforces;
- **canonical quest flags**, which `set_quest_flag` validates;
- a **"Story so far"** block in the DM prompt, built in code from flags;
- **endings** derived in code: `game_over` is `victory` or `defeat`;
- the full content set: 6 new lorebooks plus `campaign.md`, 2 updated lorebooks, bestiary additions, and 6 new and 2 updated NPC cards;
- the **scene image fix** before M7b's art lands.

All of it is deployed and smoke-played on the live stack.

**Architecture:**
- **`rpg.campaign`** (new, pure) holds the story rules: `CANONICAL_FLAGS`, `FLAG_HINTS`, `validate_flag`, `act`, `story_so_far` and `game_over`.
- **`rpg.world.Location`** gains `gates: dict[exit_id, required_flag]` and `barrier(exit, flags)`.
- **`rpg.state.apply_changes`** enforces the rules:
  - it refuses gated moves and non-canonical flags;
  - being downed at Silo's Keep sets `defeated_by_silo` instead of waking at the inn;
  - Marta at disposition ≥ +1 sets the code-owned `marta_trusts_you`.
- **The tools** (`move_to`, `set_quest_flag`) give in-world errors naming what's missing.
- **The graph** sets `turn.game_over` from `campaign.game_over(flags)`, and the prompt gains "Story so far".
- **Content tasks are test-first.** `dm/tests/test_content.py` pins the required headings, word limits, must-include facts, canonical flag names and DM rules. The prose is then written to pass it.

**Tech Stack:** the existing `dm/` (Python, LangGraph), `content/`, the `pipelines/` ingest, and `app/` (one small React fix).

**Spec:** `docs/superpowers/specs/2026-10-17-campaign-design.md` (the story bible) and the parent `2026-10-16-databricks-rpg-design.md`. This builds on M4 (`m4-game-app`, PR #6). Execution branches from `m4-game-app` with the bible commit cherry-picked in, until PR #6 merges.

## Global Constraints

- Location ids are `medallion-inn`, `delta-crossing`, `unity-archive`, `spark-forge`, `streaming-falls`, `photon-mines`, `data-swamp` and `silos-keep`. They have to match exactly across `rpg.world`, `content/manifest.yaml`, the lorebooks and the NPC homes.
- **Canonical flags are exactly bible §6**, plus two code-owned flags, `marta_trusts_you` and `defeated_by_silo`, and the existing `times_downed`. Code-owned flags can't be set through `set_quest_flag`.
- **Gates are exactly bible §3.** A refusal names what's missing in-world, using `FLAG_HINTS`, and never shows a raw flag name to the player.
- The lorebooks are 250–550 words each: an H1 title and at least 3 `##` sections, in British English, Sparkia played straight. No `TODO` or `TBD` anywhere in `content/`.
- `campaign.md` is the only document that may reveal that Silo was Aldric's master, and it carries the DM rule not to reveal it before Act 3.
- Commit messages end with `Co-authored-by: Isaac <no-reply@databricks.com>`. Commits go in their own shell command.

**Spec deltas (recorded in Task 7):**
1. The bible's "Charm DC 12 if Marta's disposition ≥ +1" is implemented as the **code-owned flag `marta_trusts_you`**. It's set when Marta's disposition first reaches +1, because the Keep's prompt can't see Marta's disposition.
2. Defeat at the Keep is the flag **`defeated_by_silo`**, set by code.
3. Snapshot `exits` gain `open: bool`.

## Review Focus

1. **The model tries to skip the story.** It moves to the Forge before Aldric speaks, takes the ferry to the Swamp without the Catalog, or sets `has_catalog` early. Moves are refused, naming the hint, and flags outside the canonical list or values are ignored with a note. Setting `has_catalog` early is the DM's job to prevent (`campaign.md` rule); the eval checks it in M6. Pinned in Tasks 1–2.
2. **The player is downed at Silo's Keep.** The adventure ends in `defeat`, rather than waking at the inn mid-finale. Downed anywhere else keeps the M3a behaviour. Pinned in Task 1.
3. **A save from sandbox mode** with non-canonical flags like `met_marta` still loads and plays. Unknown stored flags are kept but ignored by the story logic. Pinned in Task 1.
4. **Spoiler leakage.** Location lorebooks never state that Silo was Aldric's master, and only `campaign.md` does. Pinned in Task 4.
5. **A location with no image file** doesn't permanently hide later images. Pinned in Task 3.

---

## File structure (end of M7a)

```
dm/rpg/campaign.py          CANONICAL_FLAGS, CODE_FLAGS, FLAG_HINTS, SEALS, validate_flag, act, story_so_far, game_over
dm/rpg/world.py             (modified) 8 locations, Location.gates + barrier()
dm/rpg/state.py             (modified) gated moves, canonical flags, Keep defeat, marta_trusts_you
dm/agent/tools/state_tools.py (modified) move_to / set_quest_flag story errors
dm/agent/dm_graph.py        (modified) turn.game_over from flags
dm/agent/prompts.py         (modified) "Story so far" block
dm/runtime/adapter.py       (modified) snapshot exits with open flag
app/client/src/game/GameScreen.tsx (modified) scene image keyed by location, shown only with a snapshot
content/lore/{unity-archive,spark-forge,streaming-falls,photon-mines,data-swamp,silos-keep,campaign}.md   new
content/lore/{medallion-inn,delta-crossing,bestiary}.md   updated
content/npcs/{keeper-aldric,ignatia-vale,the-echo,odo-brack,warden-grisle,lord-silo}.yaml   new; marta-quill, the-sweeper updated
content/manifest.yaml       (modified) 8 locations, exits with requires, all documents
dm/tests/test_campaign.py, test_content.py (new); test_state.py, test_state_tools.py, test_store.py, test_manifest_sync.py, test_world.py (modified)
dm/scripts/campaign_smoke.sh   Act 1 live smoke with gate probe
```

---

### Task 1: Story rules (`rpg.campaign`), gated locations and state rules

**Files:**
- Create: `dm/rpg/campaign.py`, `dm/tests/test_campaign.py`
- Modify: `dm/rpg/world.py`, `dm/rpg/state.py`, `dm/tests/test_state.py`, `dm/tests/test_store.py`, `dm/tests/test_world.py`

**Interfaces:**
- Produces:
  - `rpg.campaign.SEALS = ("seal_forge", "seal_falls", "seal_mines")`
  - `CANONICAL_FLAGS: dict[str, tuple[str, ...]]`, the bible §6 values. `silo_wounds` takes `("0","1","2","3")`, and `times_downed`'s values aren't checked (it's code-owned).
  - `CODE_FLAGS = {"times_downed", "marta_trusts_you", "defeated_by_silo"}`
  - `FLAG_HINTS: dict[str, str]`, which turns a gate flag into an in-world reason
  - `validate_flag(flag, value) -> str | None`, which returns an error message, or `None` if the flag and value are valid
  - `act(flags) -> int`, which gives 1, 2 or 3
  - `story_so_far(flags, location_id) -> str`
  - `game_over(flags) -> "victory" | "defeat" | None`
  - `rpg.world.Location(id, name, description, exits, gates: dict[str, str] = {})` and `Location.barrier(exit_id, flags) -> str | None` (the unmet required flag)
  - `LOCATIONS` holds all 8 locations, with the gates from bible §3

- [ ] **Step 1: Write the failing tests**

`dm/tests/test_campaign.py`:
```python
from rpg.campaign import CANONICAL_FLAGS, CODE_FLAGS, FLAG_HINTS, SEALS, act, game_over, story_so_far, validate_flag


def test_canonical_flags_match_the_bible():
    assert set(SEALS) <= set(CANONICAL_FLAGS)
    for f in ["vowed_to_find_aldric", "saw_the_diversion", "spoke_with_aldric", "knows_cellar_route",
              "forge_regret_shared", "echo_saw_past_life", "crew_rescued", "has_catalog",
              "aldric_forgives_silo", "grisle_outcome", "silo_wounds", "ending"]:
        assert f in CANONICAL_FLAGS, f
    assert CANONICAL_FLAGS["grisle_outcome"] == ("fought", "bribed", "bluffed")
    assert CANONICAL_FLAGS["ending"] == ("might", "wits", "charm")


def test_validate_flag():
    assert validate_flag("seal_forge", "yes") is None
    assert "unknown" in validate_flag("met_marta", "yes")
    assert "must be one of" in validate_flag("ending", "victory")
    assert "set by the realm" in validate_flag("defeated_by_silo", "yes")
    assert CODE_FLAGS == {"times_downed", "marta_trusts_you", "defeated_by_silo"}


def test_acts():
    assert act({}) == 1
    assert act({"spoke_with_aldric": "yes"}) == 2
    assert act({"spoke_with_aldric": "yes", **{s: "yes" for s in SEALS}}) == 3
    assert act({"has_catalog": "yes"}) == 3


def test_story_so_far_tracks_progress():
    one = story_so_far({"vowed_to_find_aldric": "yes"}, "medallion-inn")
    assert one.startswith("Act 1") and "Unity Archive" in one and "vowed" in one
    two = story_so_far({"spoke_with_aldric": "yes", "seal_forge": "yes"}, "unity-archive")
    assert two.startswith("Act 2") and "Forge ✓" in two and "Falls ✗" in two and "Mines ✗" in two
    ready = story_so_far({"spoke_with_aldric": "yes", **{s: "yes" for s in SEALS}}, "photon-mines")
    assert ready.startswith("Act 3") and "open the vault" in ready
    carrying = story_so_far({"has_catalog": "yes"}, "delta-crossing")
    assert "downstream ferry" in carrying
    finale = story_so_far({"has_catalog": "yes", "silo_wounds": "1", "forge_regret_shared": "yes"}, "silos-keep")
    assert "Finale" in finale and "wounds 1/3" in finale and "Wits DC 12" in finale and "Charm: not yet possible" in finale


def test_game_over():
    assert game_over({}) is None
    assert game_over({"ending": "charm"}) == "victory"
    assert game_over({"defeated_by_silo": "yes"}) == "defeat"


def test_every_gate_flag_has_an_in_world_hint():
    from rpg.world import LOCATIONS

    for loc in LOCATIONS.values():
        for flag in loc.gates.values():
            assert flag in FLAG_HINTS and "_" not in FLAG_HINTS[flag]
```
Append to `dm/tests/test_world.py`:
```python
def test_eight_locations_with_bible_gates():
    from rpg.world import LOCATIONS

    assert set(LOCATIONS) == {"medallion-inn", "delta-crossing", "unity-archive", "spark-forge",
                              "streaming-falls", "photon-mines", "data-swamp", "silos-keep"}
    archive = LOCATIONS["unity-archive"]
    assert archive.barrier("spark-forge", {}) == "spoke_with_aldric"
    assert archive.barrier("spark-forge", {"spoke_with_aldric": "yes"}) is None
    assert archive.barrier("delta-crossing", {}) is None
    assert LOCATIONS["delta-crossing"].barrier("data-swamp", {}) == "has_catalog"
    assert LOCATIONS["medallion-inn"].barrier("unity-archive", {}) == "knows_cellar_route"
    for loc in LOCATIONS.values():
        assert set(loc.gates) <= set(loc.exits)
        for e in loc.exits:
            assert loc.id in LOCATIONS[e].exits, f"{loc.id}->{e} has no way back"
```
Append to `dm/tests/test_state.py`:
```python
def test_gated_move_is_barred_with_reason():
    s, notes = apply_changes(state(location_id="unity-archive", npcs=[]), [{"kind": "move", "location_id": "spark-forge"}])
    assert s.location_id == "unity-archive"
    assert any("barred" in n and "Aldric" in n for n in notes)
    s2, _ = apply_changes(state(location_id="unity-archive", npcs=[], flags={"spoke_with_aldric": "yes"}),
                          [{"kind": "move", "location_id": "spark-forge"}])
    assert s2.location_id == "spark-forge"


def test_non_canonical_and_code_owned_flags_are_ignored():
    s, notes = apply_changes(state(), [{"kind": "flag", "flag": "met_marta", "value": "yes"},
                                       {"kind": "flag", "flag": "defeated_by_silo", "value": "yes"},
                                       {"kind": "flag", "flag": "seal_forge", "value": "yes"}])
    assert s.flags == {"seal_forge": "yes"}
    assert sum("ignored" in n for n in notes) == 2


def test_old_sandbox_flags_survive_loading():
    s, _ = apply_changes(state(flags={"met_marta": "yes"}), [{"kind": "character", "xp_delta": 1}])
    assert s.flags["met_marta"] == "yes"


def test_downed_at_silos_keep_is_defeat_not_waking_at_the_inn():
    s, notes = apply_changes(state(location_id="silos-keep", npcs=[]), [{"kind": "character", "hp_delta": -40}])
    assert s.location_id == "silos-keep" and s.flags["defeated_by_silo"] == "yes"
    assert any("Lord Silo" in n for n in notes)


def test_marta_trust_sets_code_flag():
    s, _ = apply_changes(state(), [{"kind": "disposition", "npc_id": "marta-quill", "delta": 1}])
    assert s.flags.get("marta_trusts_you") == "yes"
```
Then update these existing tests to use canonical flags:
- In `dm/tests/test_state.py`:
  - in `test_xp_and_flag`, replace `"met_sweeper"` with `"saw_the_diversion"` in both the change and the assertions;
  - in `test_move_to_exit_and_reject_non_exit`, replace `"unity-archive"` with `"silos-keep"`.
- In `dm/tests/test_store.py`'s `test_commit_persists_all_kinds_of_change`, replace `{"kind": "flag", "flag": "met_marta", "value": "yes"}` and the expected `{"met_marta": "yes"}` with `saw_the_diversion`. The Marta +1 disposition also sets `marta_trusts_you`, so the expected flags become `{"saw_the_diversion": "yes", "marta_trusts_you": "yes"}`.

- [ ] **Step 2: Run them and check they fail**

Run: `cd dm && uv run pytest tests/test_campaign.py tests/test_world.py tests/test_state.py tests/test_store.py -q`
Expected: FAIL. You'll see `ModuleNotFoundError: No module named 'rpg.campaign'`, along with failures on the missing locations and gates.

- [ ] **Step 3: Implement `rpg.campaign`**

`dm/rpg/campaign.py`:
```python
"""The story's rules (spec: docs/superpowers/specs/2026-10-17-campaign-design.md). Pure functions."""

SEALS = ("seal_forge", "seal_falls", "seal_mines")
YES = ("yes",)

CANONICAL_FLAGS: dict[str, tuple[str, ...]] = {
    "vowed_to_find_aldric": YES, "saw_the_diversion": YES, "spoke_with_aldric": YES,
    "knows_cellar_route": YES, "seal_forge": YES, "forge_regret_shared": YES, "seal_falls": YES,
    "echo_saw_past_life": YES, "seal_mines": YES, "crew_rescued": YES, "has_catalog": YES,
    "aldric_forgives_silo": YES, "grisle_outcome": ("fought", "bribed", "bluffed"),
    "silo_wounds": ("0", "1", "2", "3"), "ending": ("might", "wits", "charm"),
    "marta_trusts_you": YES, "defeated_by_silo": YES, "times_downed": (),
}
CODE_FLAGS = {"times_downed", "marta_trusts_you", "defeated_by_silo"}

FLAG_HINTS = {
    "spoke_with_aldric": "Keeper Aldric has not yet spoken to you through the Archive doors",
    "knows_cellar_route": "you know of no way through the inn's locked cellar",
    "has_catalog": "you do not yet carry the Lost Catalog",
}

_SEAL_NAMES = {"seal_forge": "Forge", "seal_falls": "Falls", "seal_mines": "Mines"}


def validate_flag(flag: str, value: str) -> str | None:
    if flag in CODE_FLAGS:
        return f"{flag} is set by the realm itself, not by the storyteller"
    if flag not in CANONICAL_FLAGS:
        return f"unknown story flag {flag}; story flags are: {', '.join(f for f in CANONICAL_FLAGS if f not in CODE_FLAGS)}"
    allowed = CANONICAL_FLAGS[flag]
    if allowed and value not in allowed:
        return f"{flag} must be one of {', '.join(allowed)}"
    return None


def _yes(flags: dict, name: str) -> bool:
    return flags.get(name) == "yes"


def act(flags: dict) -> int:
    if _yes(flags, "has_catalog") or all(_yes(flags, s) for s in SEALS):
        return 3
    return 2 if _yes(flags, "spoke_with_aldric") else 1


def story_so_far(flags: dict, location_id: str) -> str:
    stage = act(flags)
    if stage == 1:
        line = "Act 1, The Sealed Archive. Goal: reach the Unity Archive beyond the Delta Crossing and learn why it is sealed."
        if _yes(flags, "vowed_to_find_aldric"):
            line += " You vowed to Marta Quill to find Keeper Aldric."
        return line
    if stage == 2:
        seals = ", ".join(f"{_SEAL_NAMES[s]} {'✓' if _yes(flags, s) else '✗'}" for s in SEALS)
        return (f"Act 2, The Three Seals. Seals: {seals}. Next: seek the remaining seals, in any order. "
                "The roads from the Unity Archive lead to the Spark Forge, the Streaming Falls and the Photon Mines.")
    if not _yes(flags, "has_catalog"):
        return "Act 3, The Lost Catalog. All three seals are yours: return to the Unity Archive to open the vault."
    if location_id != "silos-keep":
        return ("Act 3, The Lost Catalog. You carry the Lost Catalog. Next: take the Sweeper's downstream ferry "
                "from the Delta Crossing to the Data Swamp, and on to Silo's Keep.")
    wounds = flags.get("silo_wounds", "0")
    wits_dc = 12 if _yes(flags, "forge_regret_shared") else 16
    if _yes(flags, "aldric_forgives_silo"):
        charm_dc = 12 if (_yes(flags, "marta_trusts_you") or _yes(flags, "echo_saw_past_life")) else 16
        charm = f"Charm DC {charm_dc}"
    else:
        charm = "Charm: not yet possible (Aldric has not forgiven Silo)"
    return (f"Finale: confront Lord Silo. Might: wound him three times (wounds {wounds}/3; set silo_wounds after each hit). "
            f"Wits: present the Catalog's proof, Wits DC {wits_dc}. {charm}. When he yields, set ending.")


def game_over(flags: dict) -> str | None:
    if _yes(flags, "defeated_by_silo"):
        return "defeat"
    return "victory" if flags.get("ending") in CANONICAL_FLAGS["ending"] else None
```

- [ ] **Step 4: The 8 locations and gates in `rpg.world`**

In `dm/rpg/world.py`:
1. Add `from dataclasses import dataclass, field`. Then replace the `Location` dataclass with:
```python
@dataclass(frozen=True)
class Location:
    id: str
    name: str
    description: str
    exits: tuple[str, ...]
    gates: dict[str, str] = field(default_factory=dict)  # exit id -> flag that must be "yes"

    def barrier(self, exit_id: str, flags: dict) -> str | None:
        required = self.gates.get(exit_id)
        return required if required and flags.get(required) != "yes" else None
```
2. Replace the whole `LOCATIONS` dict with:
```python
LOCATIONS: dict[str, Location] = {
    START_LOCATION_ID: Location(
        id=START_LOCATION_ID,
        name="The Medallion Inn, Lakehouse Village",
        description=(
            "A three-storey coaching inn at the heart of Lakehouse Village in the Kingdom of "
            "Sparkia. Its rooms are named Bronze, Silver and Gold, from the draughty attic to "
            "the gilded suite. Travellers swap rumours by the fire: the Delta river has begun "
            "running backwards some nights, and the Unity Archive has sealed its doors. The "
            "innkeeper, Marta Quill, knows everyone's business and sells it by the half-pint."
        ),
        exits=("delta-crossing", "unity-archive"),
        gates={"unity-archive": "knows_cellar_route"},
    ),
    "delta-crossing": Location(
        id="delta-crossing",
        name="The Delta Crossing",
        description=(
            "A wide, cold ford where the river Delta runs in visible layers, each current a "
            "different day. A rope ferry worked by a silent ferryman called the Sweeper crosses "
            "to the road for the Unity Archive. Upstream stand the broken piers of the old bridge."
        ),
        exits=("medallion-inn", "unity-archive", "data-swamp"),
        gates={"data-swamp": "has_catalog"},
    ),
    "unity-archive": Location(
        id="unity-archive",
        name="The Unity Archive",
        description=(
            "The great library of Sparkia, a hill of grey stone and bronze doors that answer only "
            "to proper writs. The doors are sealed. Behind them, Keeper Aldric guards the vault. "
            "Three roads leave its courtyard for the realm's great houses."
        ),
        exits=("delta-crossing", "spark-forge", "streaming-falls", "photon-mines", "medallion-inn"),
        gates={"spark-forge": "spoke_with_aldric", "streaming-falls": "spoke_with_aldric",
               "photon-mines": "spoke_with_aldric", "medallion-inn": "knows_cellar_route"},
    ),
    "spark-forge": Location(
        id="spark-forge",
        name="The Spark Forge",
        description=(
            "A tower of furnaces where Sparkia's mages learn to kindle. Apprentices work in rings "
            "around a single great flame. Forgemaster Ignatia Vale holds the Forge Seal."
        ),
        exits=("unity-archive",),
    ),
    "streaming-falls": Location(
        id="streaming-falls",
        name="The Streaming Falls",
        description=(
            "A curtain of water that never stops, where the river's memory spills into mist. In "
            "the spray, shapes replay what travellers once did. The Echo keeps the Falls Seal."
        ),
        exits=("unity-archive",),
    ),
    "photon-mines": Location(
        id="photon-mines",
        name="The Photon Mines",
        description=(
            "Deep galleries lit by ore that shines like trapped light. The tunnels shift after "
            "every collapse, and miners chalk each turn on the walls. Shiftmaster Odo Brack holds "
            "the Mines Seal."
        ),
        exits=("unity-archive",),
    ),
    "data-swamp": Location(
        id="data-swamp",
        name="The Data Swamp",
        description=(
            "A sprawling fen where walled-away records rot into mud and the water runs every way "
            "at once. Swamp rats, Orphans and worse lurk here, and Warden Grisle keeps the road to "
            "Silo's Keep."
        ),
        exits=("delta-crossing", "silos-keep"),
        gates={"silos-keep": "has_catalog"},
    ),
    "silos-keep": Location(
        id="silos-keep",
        name="Silo's Keep",
        description=(
            "A fortress of walled-up books rising from the swamp, its corridors bricked shut with "
            "volumes. At its heart, Lord Silo keeps the realm's knowledge from everyone."
        ),
        exits=("data-swamp",),
    ),
}
```

- [ ] **Step 5: State rules in `rpg.state`**

In `dm/rpg/state.py`:
1. Add `from rpg.campaign import FLAG_HINTS, validate_flag`.
2. Replace `_downed` with:
```python
def _downed(state: GameState, notes: list[str]) -> None:
    c = state.character
    if state.location_id == "silos-keep":
        state.flags["defeated_by_silo"] = "yes"
        notes.append("defeated by Lord Silo: the walls close over you")
        return
    c.hp = c.max_hp // 2
    c.gold = c.gold // 2
    state.location_id = START_LOCATION_ID
    state.flags["times_downed"] = str(int(state.flags.get("times_downed", "0")) + 1)
    notes.append(f"downed: woke at {LOCATIONS[START_LOCATION_ID].name} with HP {c.hp} and {c.gold} gold")
```
3. In `apply_changes`, replace the `FlagChange` branch with:
```python
        elif isinstance(ch, FlagChange):
            problem = validate_flag(ch.flag, ch.value)
            if problem:
                notes.append(f"ignored flag {ch.flag}: {problem}")
                continue
            new.flags[ch.flag] = ch.value
            notes.append(f"flag {ch.flag} = {ch.value}")
```
4. In the `DispositionChange` branch, after `npc.disposition = after`, add:
```python
                    if npc.npc_id == "marta-quill" and after >= 1:
                        new.flags["marta_trusts_you"] = "yes"
```
5. Replace the `MoveChange` branch with:
```python
        elif isinstance(ch, MoveChange):
            here = LOCATIONS[new.location_id]
            barrier = here.barrier(ch.location_id, new.flags)
            if ch.location_id not in here.exits or ch.location_id not in LOCATIONS:
                notes.append(f"cannot reach {ch.location_id} from {here.name}")
            elif barrier:
                notes.append(f"barred from {LOCATIONS[ch.location_id].name}: {FLAG_HINTS.get(barrier, 'the way is shut')}")
            else:
                new.location_id = ch.location_id
                notes.append(f"moved to {LOCATIONS[ch.location_id].name}")
```

- [ ] **Step 6: Run the tests**

Run: `cd dm && uv run pytest -q`
Expected: everything passes except `tests/test_manifest_sync.py`, which fails because the manifest still lists 2 locations. That's fixed in Task 4. Record the ledger note "manifest sync red until Task 4".

- [ ] **Step 7: Commit**

```bash
git add dm/rpg dm/tests
git commit -m "feat(rpg): campaign rules: canonical flags, gated exits across 8 locations, Keep defeat, story so far

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 2: Story-aware tools, prompt, endings and snapshot

**Files:**
- Modify: `dm/agent/tools/state_tools.py`, `dm/agent/prompts.py`, `dm/agent/dm_graph.py`, `dm/runtime/adapter.py`
- Test: `dm/tests/test_state_tools.py`, `dm/tests/test_dm_graph.py`, `dm/tests/test_agent.py` (append and modify)

**Interfaces:**
- Produces:
  - `move_to` errors become `{"error": "The way to <Name> is barred: <hint>."}` for gated exits, or `"cannot reach <id>; exits: [...]"` for non-exits.
  - `set_quest_flag` errors are `{"error": validate_flag(...)}`.
  - The DM system prompt gains `Story so far: <campaign.story_so_far(flags, location_id)>`.
  - `compose` sets `turn["game_over"] = campaign.game_over(flags after commit)`.
  - Snapshot `exits` become `[{id, name, open: bool}]`.

- [ ] **Step 1: Write the failing tests**

Append to `dm/tests/test_state_tools.py`:
```python
def test_move_to_gated_exit_is_barred_in_world():
    gated = {**STATE, "location_id": "unity-archive", "flags": {}}
    out = move_to.invoke({"name": "move_to", "args": {"location_id": "spark-forge", "state": gated},
                          "id": "c1", "type": "tool_call"})
    content = json.loads(out.update["messages"][0].content)
    assert "barred" in content["error"] and "Aldric" in content["error"]
    assert "staged" not in out.update


def test_set_quest_flag_rejects_non_canonical():
    content, staged = call(set_quest_flag, flag="met_marta", value="yes")
    assert "unknown story flag" in content["error"] and staged == []
    content, staged = call(set_quest_flag, flag="ending", value="victory")
    assert "must be one of" in content["error"] and staged == []
```
In `dm/tests/test_state_tools.py`, change the existing `test_quest_flag_validates_slug` first assertion to use `flag="saw_the_diversion"`, with the matching expected dict.

Append to `dm/tests/test_dm_graph.py`:
```python
def test_story_so_far_is_in_the_dm_prompt():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    run(make(model), "Hello")
    assert "Story so far: Act 1" in model.reason_calls[0][0].content


def test_ending_flag_sets_victory():
    from agent.tools.state_tools import set_quest_flag

    store = new_store()
    game = store.load("t1")
    game.location_id = "silos-keep"
    game.flags.update({"has_catalog": "yes"})
    store.commit("t1", game)
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[tc("set_quest_flag", flag="ending", value="charm")]), AIMessage(content="d")],
        structured=[PROSE],
    )
    turn = run(make(model, [roll_check, set_quest_flag], store), "I offer Silo Aldric's letters.")["turn"]
    assert turn["game_over"] == "victory"
```
Append to `dm/tests/test_agent.py`:
```python
def test_snapshot_exits_show_which_are_open(mem_store):
    from runtime.adapter import game_snapshot

    game = mem_store.create_adventure("s-x", "p", "Brannoc", "warrior")
    exits = {e["id"]: e["open"] for e in game_snapshot(game)["exits"]}
    assert exits == {"delta-crossing": True, "unity-archive": False}
```
Then update `test_turn_emits_and_returns_game_snapshot_without_secrets` in `dm/tests/test_agent.py`: its expected `exits` becomes `[{"id": "delta-crossing", "name": "The Delta Crossing", "open": True}, {"id": "unity-archive", "name": "The Unity Archive", "open": False}]`.

- [ ] **Step 2: Run them and check they fail**

Run: `cd dm && uv run pytest tests/test_state_tools.py tests/test_dm_graph.py tests/test_agent.py -q`
Expected: the new tests fail, with assertion errors on the error text, the missing "Story so far", `game_over` being None, and the missing `open` key.

- [ ] **Step 3: Implement**

1. In `dm/agent/tools/state_tools.py`, add `from rpg.campaign import FLAG_HINTS, validate_flag`. Then:
   - In `set_quest_flag`, before `return _stage(...)`, add:
     ```python
         problem = validate_flag(flag, value)
         if problem:
             return reply("set_quest_flag", tool_call_id, {"error": problem})
     ```
   - In `move_to`, after the non-exit check, add:
     ```python
         barrier = here.barrier(location_id, state.get("flags") or {})
         if barrier:
             name = LOCATIONS[location_id].name
             return reply("move_to", tool_call_id, {"error": f"The way to {name} is barred: {FLAG_HINTS.get(barrier, 'the way is shut')}."})
     ```
2. In `dm/agent/prompts.py`, add `from rpg.campaign import story_so_far`. In `DM_SYSTEM`, insert the line `Story so far: {story}` followed by a blank line, directly above `The player character:`. In `render_dm_system`, pass `story=story_so_far(game.flags, game.location_id)` to `format`.
3. In `dm/agent/dm_graph.py`, add `from rpg.campaign import game_over`. In `compose`, right after the `turn` is decided and before `text = ...`, add `turn.game_over = game_over(state.get("flags") or {})`.
4. In `dm/runtime/adapter.py`, in `game_snapshot`, replace the `exits` entry with:
```python
        "exits": [{"id": e, "name": LOCATIONS[e].name, "open": here.barrier(e, game.flags) is None}
                  for e in here.exits if e in LOCATIONS],
```

- [ ] **Step 4: Run the tests**

Run: `cd dm && uv run pytest -q --deselect tests/test_manifest_sync.py && uvx ruff check agent rpg runtime --select F`
Expected: everything passes, and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
git add dm
git commit -m "feat(dm): story-aware move_to/set_quest_flag, Story so far in the prompt, endings set game_over

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 3: The scene image fix (before the art lands)

**Files:**
- Modify: `app/client/src/game/GameScreen.tsx`
- Test: `app/client/src/game/scene.test.ts` (new) and `app/client/src/game/scene.ts` (new)

**Interfaces:**
- Produces: `sceneImage(locationId: string | undefined): string | null`. It returns `/images/${id}.webp` for a known id and `null` for none. The game screen renders `<img key={id} …>` only when `sceneImage` is non-null, so a 404 hides that one image only, and a new location gets a fresh element.

- [ ] **Step 1: Write the failing test**

`app/client/src/game/scene.test.ts`:
```typescript
import { describe, expect, it } from 'vitest';
import { sceneImage } from './scene';

describe('sceneImage', () => {
  it('maps a location to its art and nothing before the snapshot arrives', () => {
    expect(sceneImage('delta-crossing')).toBe('/images/delta-crossing.webp');
    expect(sceneImage(undefined)).toBeNull();
    expect(sceneImage('')).toBeNull();
  });
});
```

- [ ] **Step 2: Run it and check it fails**

Run: `cd app && npx vitest run client/src/game/scene.test.ts`
Expected: FAIL with `Cannot find module './scene'`.

- [ ] **Step 3: Implement**

`app/client/src/game/scene.ts`:
```typescript
export function sceneImage(locationId: string | undefined): string | null {
  return locationId ? `/images/${locationId}.webp` : null;
}
```
In `app/client/src/game/GameScreen.tsx`, add `import { sceneImage } from './scene';`, and replace the `<img …/>` line with:
```tsx
            {sceneImage(view.game?.location_id) && (
              <img key={view.game?.location_id} src={sceneImage(view.game?.location_id) ?? ''} alt=""
                   onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')} />
            )}
```

- [ ] **Step 4: Test, typecheck and lint**

Run: `cd app && npm test && npm run typecheck && npm run lint`
Expected: 23 tests pass, and the typecheck and lint are clean.

- [ ] **Step 5: Commit**

```bash
git add app/client/src/game
git commit -m "fix(app): scene image keyed by location and rendered only with a snapshot (a 404 no longer hides later art)

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 4: Content (lorebooks, campaign.md, bestiary and manifest), test-first

**Files:**
- Create: `dm/tests/test_content.py`, plus `content/lore/unity-archive.md`, `spark-forge.md`, `streaming-falls.md`, `photon-mines.md`, `data-swamp.md`, `silos-keep.md` and `campaign.md`
- Modify: `content/lore/medallion-inn.md`, `content/lore/delta-crossing.md`, `content/lore/bestiary.md`, `content/manifest.yaml`, `dm/tests/test_manifest_sync.py`

**Interfaces:**
- Consumes: bible §§2–6, `rpg.world.LOCATIONS`, `rpg.campaign.CANONICAL_FLAGS`
- Produces: the manifest's `locations[].exits` change from a list of ids to a list of `{to: <id>, requires?: <flag>}`. The `documents` list adds the 6 new lorebooks (`doc_type: location`) and `campaign.md` (`doc_type: primer`, `location_id: global`).

- [ ] **Step 1: Write the failing content tests**

`dm/tests/test_content.py`:
```python
"""Content contract: the story bible's facts must be in the lorebooks the DM retrieves."""

import re
from pathlib import Path

import pytest
from rpg.campaign import CANONICAL_FLAGS, CODE_FLAGS
from rpg.world import LOCATIONS

LORE = Path(__file__).resolve().parents[2] / "content" / "lore"

MUST_INCLUDE = {
    "medallion-inn": ["Marta Quill", "cellar", "running water", "ledger"],
    "delta-crossing": ["the Sweeper", "downstream", "older current"],
    "unity-archive": ["writ", "Keeper Aldric", "three seals", "vault", "undercroft"],
    "spark-forge": ["Trial of Kindling", "Ignatia Vale", "spark", "Forge Seal"],
    "streaming-falls": ["the Echo", "echoes", "choices", "Falls Seal"],
    "photon-mines": ["chalk", "Odo Brack", "crew", "Mines Seal"],
    "data-swamp": ["Warden Grisle", "Swamp rats", "Orphans", "river wraith"],
    "silos-keep": ["Lord Silo", "walled", "letters"],
}


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z']+", text))


@pytest.mark.parametrize("location_id", sorted(LOCATIONS))
def test_location_lorebook_shape_and_facts(location_id):
    text = (LORE / f"{location_id}.md").read_text()
    assert text.startswith("# "), "needs an H1 title"
    assert text.count("\n## ") >= 3, "needs at least three sections"
    assert 250 <= words(text) <= 550, f"{words(text)} words"
    for fact in MUST_INCLUDE[location_id]:
        assert fact.lower() in text.lower(), f"{location_id} must mention {fact!r}"


@pytest.mark.parametrize("location_id", sorted(LOCATIONS))
def test_no_spoiler_outside_campaign(location_id):
    text = (LORE / f"{location_id}.md").read_text().lower()
    assert "aldric's master" not in text and "was aldric's" not in text


def test_campaign_md_carries_acts_flags_and_rules():
    text = (LORE / "campaign.md").read_text()
    for heading in ["## Act 1", "## Act 2", "## Act 3", "## Endings", "## Rules for the Dungeon Master"]:
        assert heading in text, heading
    for flag in CANONICAL_FLAGS:
        if flag not in CODE_FLAGS:
            assert f"`{flag}`" in text, f"campaign.md must name {flag}"
    for rule in ["Never reveal", "Offer, never force", "only quotes the player", "earned"]:
        assert rule in text, rule
    for loc in LOCATIONS.values():
        assert loc.name.split(",")[0] in text, loc.name


def test_bestiary_has_new_foes_with_stats():
    text = (LORE / "bestiary.md").read_text()
    for foe in ["Silenced Archivist", "Sealing Warden", "Warden Grisle", "Lord Silo"]:
        assert foe in text, foe
    assert text.count("Hit points") >= 7


def test_no_placeholders_in_content():
    for p in (LORE.parent).rglob("*"):
        if p.is_file() and p.suffix in {".md", ".yaml"}:
            assert not re.search(r"\b(TODO|TBD|FIXME)\b", p.read_text()), p.name
```
Replace `dm/tests/test_manifest_sync.py`'s `test_manifest_locations_match_world` with:
```python
def test_manifest_locations_and_gates_match_world():
    m = load()
    manifest = {loc["id"]: {e["to"]: e.get("requires") for e in loc["exits"]} for loc in m["locations"]}
    world = {loc.id: {e: loc.gates.get(e) for e in loc.exits} for loc in LOCATIONS.values()}
    assert manifest == world
```

- [ ] **Step 2: Run them and check they fail**

Run: `cd dm && uv run pytest tests/test_content.py tests/test_manifest_sync.py -q`
Expected: FAIL. The new lorebook files are missing, the facts are missing from the existing books, and the manifest is out of sync.

- [ ] **Step 3: Write the manifest**

Rewrite `content/manifest.yaml` so that:
- `documents` has 13 entries: the existing 5, plus `unity-archive.md`, `spark-forge.md`, `streaming-falls.md`, `photon-mines.md`, `data-swamp.md` and `silos-keep.md` (each `doc_type: location` with `location_id` = its id), plus `campaign.md` (`doc_type: primer`, `location_id: global`);
- `locations` has 8 entries (id, name, lorebook, exits), with exits in the `{to, requires}` form, exactly mirroring `rpg.world.LOCATIONS` from Task 1.

- [ ] **Step 4: Write and update the lorebooks**

Write each one to satisfy the tests and the bible. Each is 300–450 words, has an H1 and 3–5 `##` sections, and is in British English, Sparkia played straight. Bible §4 is the brief for each location, and §5 gives the NPC facts. The specifics:
- **`medallion-inn.md`:**
  - add a "Marta's Ledger" section: every traveller is written down, and Marta remembers returning faces;
  - keep the existing cellar and water lines (these hint at the cellar route without revealing where it goes);
  - stay within 550 words.
- **`delta-crossing.md`:**
  - add that the Sweeper can show you an older current to those he trusts;
  - add that he also runs a downstream ferry, but only for "those who carry what the river is owed".
- **`unity-archive.md`:**
  - writs and wards (which ignore tricks, lies and "magic words");
  - the bronze doors;
  - Aldric's voice through them;
  - the three seals of the great houses;
  - the vault;
  - the undercroft, where water runs under the Archive from somewhere far off.
- **`spark-forge.md`:**
  - the Trial of Kindling, where one spark is split across many hands;
  - Ignatia Vale;
  - the Forge Seal, given to anyone who shares rather than hoards;
  - a hint that the forge once made a darker fire.
- **`streaming-falls.md`:**
  - the falls replay echoes of travellers' choices;
  - the Echo speaks only in a visitor's own words;
  - the Falls Seal, earned by honestly facing what the falls show.
- **`photon-mines.md`:**
  - light-ore, collapses, and chalk marks on every turn;
  - Odo Brack and his trapped crew;
  - the Mines Seal;
  - strangers digging toward "the old foundations".
- **`data-swamp.md`:**
  - rotting walled-up records;
  - Swamp rats, Orphans and a river wraith (refer to the bestiary for stats);
  - Warden Grisle on the causeway to the Keep;
  - the swamp grows as records are hoarded.
- **`silos-keep.md`:**
  - walled corridors of bricked books;
  - Lord Silo, weary and certain;
  - a study full of old letters.
  - **Don't** say whose letters they are, or that he was Aldric's master.
- **`campaign.md`:**
  - an H1;
  - `## Premise`;
  - `## Act 1`, `## Act 2` and `## Act 3`;
  - `## Endings`, with the exact DCs from bible §6;
  - `## Rules for the Dungeon Master`, with bible §7's five rules verbatim;
  - every non-code flag named in backticks, with when to set it.

  `campaign.md` is the only document that may say Silo was Aldric's master, and it carries the rule not to reveal that before Act 3.
- **`bestiary.md`:**
  - append the four foes with stats in the existing format (bible §5);
  - add short notable-folk entries for Ignatia Vale, the Echo and Odo Brack.

- [ ] **Step 5: Run the tests**

Run: `cd dm && uv run pytest -q && cd ../pipelines && uv run pytest -q`
Expected: every DM test passes, including the new content and manifest-sync tests. All pipelines tests pass, and `test_every_lorebook_renders` covers the new books.

- [ ] **Step 6: Commit**

```bash
git add content dm/tests/test_content.py dm/tests/test_manifest_sync.py
git commit -m "feat(content): the full adventure: 6 new lorebooks, campaign.md, bestiary foes and the 8-location manifest

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 5: NPC cards

**Files:**
- Create: `content/npcs/keeper-aldric.yaml`, `ignatia-vale.yaml`, `the-echo.yaml`, `odo-brack.yaml`, `warden-grisle.yaml` and `lord-silo.yaml`
- Modify: `content/npcs/marta-quill.yaml`, `content/npcs/the-sweeper.yaml`, `dm/tests/test_store.py` (the NPC count)
- Test: `dm/tests/test_content.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `dm/tests/test_content.py`:
```python
def test_npc_cards_cover_the_cast():
    from rpg.store import load_npc_cards

    cards = {c.npc_id: c for c in load_npc_cards(LORE.parent / "npcs")}
    assert set(cards) == {"marta-quill", "the-sweeper", "keeper-aldric", "ignatia-vale", "the-echo",
                          "odo-brack", "warden-grisle", "lord-silo"}
    for c in cards.values():
        assert c.home_location_id in LOCATIONS
        assert len(c.persona) > 80 and len(c.speech_style) > 30 and len(c.secrets) > 40
    assert "undercroft" in cards["marta-quill"].secrets
    assert "master" in cards["keeper-aldric"].secrets
    assert "letters" in cards["lord-silo"].secrets
```
Also update `dm/tests/test_store.py`'s `test_load_npc_cards` to expect the 8 ids in filename order: `["ignatia-vale", "keeper-aldric", "lord-silo", "marta-quill", "odo-brack", "the-echo", "the-sweeper", "warden-grisle"]`.

- [ ] **Step 2: Run them and check they fail**

Run: `cd dm && uv run pytest tests/test_content.py tests/test_store.py -q`
Expected: FAIL, because the card set doesn't match.

- [ ] **Step 3: Write the cards**

Use the existing YAML format (`npc_id`, `name`, `home_location_id`, `persona`, `speech_style`, `secrets`), following bible §5 (wants, secret, why it matters):
- **Marta:** her secret now says the cellar water reaches the Archive's undercroft, and that she'll show it only to someone she trusts deeply (disposition +2), in which case the DM sets `knows_cellar_route`.
- **The Sweeper:** his secret includes the vision of Silo's wardens diverting the river, and the downstream ferry for whoever carries the Lost Catalog.
- **Aldric** (unity-archive): his voice comes through the doors in Act 1, and he's met in person in Act 3. His secret: Silo was his master, and he helped raise the first walls.
- **Ignatia** (spark-forge), **the Echo** (streaming-falls), **Odo** (photon-mines), **Grisle** (data-swamp) and **Silo** (silos-keep): wants, secrets and speech styles as in the bible table. The Echo's speech style is "only ever repeats the visitor's own words back".

- [ ] **Step 4: Run the tests**

Run: `cd dm && uv run pytest -q`
Expected: everything passes.

- [ ] **Step 5: Commit**

```bash
git add content/npcs dm/tests
git commit -m "feat(content): NPC cards for the full cast (Aldric, Ignatia, the Echo, Odo, Grisle, Silo)

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 6: Deploy the adventure and smoke Act 1 live

**Files:**
- Create: `dm/scripts/campaign_smoke.sh`

- [ ] **Step 1: Deploy everything**

Run: `make deploy PROFILE=brickbots CATALOG=serverless_stable_brickbots_catalog`
Expected:
- 12 PDFs render (11 lorebooks plus `campaign.md`).
- The ingest re-indexes, with more chunks than the previous 27.
- `make db` seeds 8 NPC cards.
- The DM deploys with 0 grant failures.
- The game app deploys.
- `git status` is clean apart from build output.

- [ ] **Step 2: Write the Act 1 smoke**

`dm/scripts/campaign_smoke.sh`:
```bash
#!/usr/bin/env bash
# Plays Act 1 against the deployed DM and probes a story gate. Prints location and flags per turn.
set -euo pipefail
BASE="${1:?usage: campaign_smoke.sh <dm-url>}"
TOKEN="${TOKEN:?set TOKEN=$(databricks auth token -p <profile> | jq -r .access_token)}"
SESSION=$(uuidgen)
turn() {
  local input="$1"
  jq -n --arg id "$(uuidgen)" --arg s "$SESSION" --argjson input "$input" '{id:$id, session_id:$s, input:$input}' |
    curl -sS --fail "$BASE/api/invocations" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d @- |
    jq -r '"📍 " + .output.game.location_id + "  flags=" + (.output.game.flags | keys | join(",")) + "  open=" + ([.output.game.exits[] | select(.open) | .id] | join(",")),
           (.output.turn.events[] | "  " + .type + ": " + .summary)'
}
msg() { jq -n --arg c "$1" '{messages:[{role:"user", content:$c}]}'; }
echo "--- new game"; turn '{"messages":[],"new_game":{"name":"Tess","archetype":"warrior"}}'
echo "--- vow";      turn "$(msg 'I promise Marta I will find Keeper Aldric.')"
echo "--- to delta"; turn "$(msg 'I head out to the Delta Crossing.')"
echo "--- archive";  turn "$(msg 'I take the road upriver to the Unity Archive.')"
echo "--- gate probe: straight to the Forge"; turn "$(msg 'Without waiting, I march straight off to the Spark Forge.')"
echo "--- doors";    turn "$(msg 'I knock on the bronze doors and call out for Keeper Aldric.')"
echo "CAMPAIGN SMOKE DONE (session $SESSION)"
```
Then `chmod +x dm/scripts/campaign_smoke.sh`.

- [ ] **Step 3: Run it**

```bash
URL=$(databricks apps get agent-bricks-dm --profile brickbots -o json | jq -r .url)
TOKEN=$(databricks auth token --profile brickbots | jq -r .access_token) dm/scripts/campaign_smoke.sh "$URL"
```
Expected (the LLM narrates, so check the state lines):
- Turn 2 sets `vowed_to_find_aldric`.
- Turn 3 shows 📍 `delta-crossing`, and turn 4 shows 📍 `unity-archive`.
- **The gate probe stays at `unity-archive`**, with no `spark-forge` in `open=`. Either the DM narrates the barred road, or a `move_to` refusal appears.
- Turn 6 sets `spoke_with_aldric`, and `open=` then includes `spark-forge,streaming-falls,photon-mines`.

If the DM doesn't set a flag the story clearly calls for, re-run once. If it still doesn't, record it in the ledger as an M6 eval scenario (story flag adherence) rather than forcing it.

- [ ] **Step 4: Check it in the browser**

Open the game app, start a new adventure, and play to the Archive. The Scrying Glass should show 📚 lookups that include `campaign`. Screenshot the moment the Forge road is barred, as `docs/design/screenshots/2026-10-17-m7a-gate.png`.

- [ ] **Step 5: Commit**

```bash
git add dm/scripts/campaign_smoke.sh docs/design/screenshots
git commit -m "test(dm): live Act 1 campaign smoke with a story-gate probe; gate screenshot

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 7: Spec deltas and docs

**Files:**
- Modify: `docs/superpowers/specs/2026-10-17-campaign-design.md`, `README.md`

- [ ] **Step 1: Bible deltas**

In the bible:
- **§6 flags table:** append the rows `| marta_trusts_you | yes | Set by code when Marta's disposition first reaches +1 |` and `| defeated_by_silo | yes | Set by code when the player is downed at silos-keep |`.
- **§6 Charm ending:** change "if Marta's disposition is +1 or more" to "if `marta_trusts_you`".
- **§9 code list:** mark items 1–5 as done in M7a.
- **Status:** set it to `Approved; implemented in M7a (art and music in M7b)`.

- [ ] **Step 2: README**

In the root `README.md`, replace the "🚧 Early days" line with:
`> 🗺️ Playable: a three-act adventure in the Kingdom of Sparkia (see the [story bible](docs/superpowers/specs/2026-10-17-campaign-design.md)). Art and music coming next.`

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs README.md
git commit -m "docs: campaign deltas (code-owned flags) and README status

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

## Done when

- `make test` and `cd app && npm test` pass (the content tests included), and the typecheck and lint are clean.
- The deployed DM plays Act 1 to `spoke_with_aldric`, and the gate probe is refused.
- The game app shows the barred road, with a screenshot saved.
- Next is M7b: Kling art, ElevenLabs music and in-game audio.
