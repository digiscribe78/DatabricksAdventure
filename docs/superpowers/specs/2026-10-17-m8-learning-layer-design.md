# Databricks Adventure: M8 The Learning Layer (Hints, End Screen, Guide)

- **Date:** 2026-10-17
- **Status:** Draft for review; to be implemented in M8
- **Parent spec:** `2026-10-16-databricks-rpg-design.md` §9 items 4 (end screen) and the concepts guide; §15 step 7. This document refines them; where they differ, this one wins.
- **Design rule:** persistent application state lives in Lakebase, not the browser. The browser holds only transient UI.

## 1. Intent

| Piece | What it does |
|---|---|
| 💡 Hints | A player who's stuck asks for a hint. Code picks the next unfinished required story beat from game state and shows a hand-written, two-tier hint. No model call, no turn used. |
| End screen | When an adventure ends: a quest summary, "what you just saw" counts (from Lakebase) linking to the Guide, and what the realm will remember (M5b's distilled memories). |
| 📖 Guide | An in-app panel with one short page per concept: what you saw, how it's built here, try this, docs. It's the concepts guide the parent spec promised, and the in-app home of "Things to try". |

## 2. Hints

### 2.1 Content: `content/hints.yaml`

```yaml
spoke_with_aldric:
  nudge: "Marta's words come back to you: the Keeper's Archive lies upriver, past the Delta Crossing."
  clearer: "Go to the Unity Archive and call out to Keeper Aldric at the bronze doors."
```

- There is one entry per **required** beat in `rpg.campaign.BEATS`. The optional beats (`knows_cellar_route`, `forge_regret_shared`, `echo_saw_past_life`, `aldric_forgives_silo`) have none.
- `crew_rescued` and `seal_mines` share one hint.
- `silo_wounds` and `ending` share one hint: "strike, outwit or out-talk Lord Silo".
- **Content tests:**
  - every required beat has a non-empty `nudge` and `clearer`;
  - no key is unknown;
  - a hint for an act-N beat names no place or person first introduced in a later act. This reuses the act-scoping data the M7a spoiler tests use.

### 2.2 Choosing: `rpg/hints.py`

```python
def next_hint(flags: dict, location_id: str) -> dict | None:
    """{"beat", "where" (location name), "nudge", "clearer"} for the next unfinished required beat, or None when the game is over."""
```

- **Candidates:** the current act's required beats (`rpg.campaign.act(flags)`) that aren't set.
- **Which one:** if a candidate's home (`FLAG_HOMES`) is the player's location, that one. Otherwise the first candidate in `BEATS` order.
  - Act 2's three seals can be done in any order, so this hints the seal where the player stands, or else the first unfinished seal.
- **No hint** (`None`) once `game_over(flags)` is set.

### 2.3 Delivery and UI

- `runtime.adapter.game_snapshot` adds `hint: next_hint(game.flags, game.location_id)`.
- **The 💡 Hint button** sits beside the text box.
  - The first press shows the nudge in an in-world box under the choices. A **Clearer hint ▸** button inside it then shows the clearer hint.
  - The box closes when the next turn starts. Which tier is showing is transient UI state.
- **Each press logs a line in the Scrying Glass:** *"💡 Hint from game state: next beat `spoke_with_aldric` at The Unity Archive"*, with a "(?)" explainer saying hints come from code reading the campaign state, not from the model.
- **Counting:** the browser counts hint presses since the last turn and sends `hints_seen: n` with the next turn's payload (§3.2).

## 3. Stats in Lakebase

### 3.1 Table

```sql
CREATE TABLE IF NOT EXISTS rpg.adventure_stats (
    adventure_id text PRIMARY KEY REFERENCES rpg.adventures (id) ON DELETE CASCADE,
    rolls int NOT NULL DEFAULT 0, attacks int NOT NULL DEFAULT 0, lore int NOT NULL DEFAULT 0,
    memories int NOT NULL DEFAULT 0, state_commits int NOT NULL DEFAULT 0, guardrails int NOT NULL DEFAULT 0,
    hints int NOT NULL DEFAULT 0, turns int NOT NULL DEFAULT 0,
    since_start boolean NOT NULL DEFAULT true,  -- false if counting began mid-adventure (pre-M8 saves)
    updated_at timestamptz NOT NULL DEFAULT now()
);
```

The table goes in `dm/rpg/schema.sql` (applied by `make db`), with the DM's existing grants on schema `rpg`.

### 3.2 Writing and reading

- `GameStore` gains two methods, in both `InMemoryStore` and `PostgresStore`:
  - `add_stats(session_id: str, counts: dict[str, int]) -> None`, an upsert that adds the counts;
  - `stats(session_id: str) -> dict | None`.
- `create_adventure` inserts the row with `since_start = true`. A first `add_stats` on an adventure with no row (a save from before M8) inserts it with `since_start = false`.
- **The adapter:** after each turn, alongside the transcript write (after the `game` snapshot goes out), it counts the turn's events by type, adds `turns: 1` and `hints: <hints_seen>`, and calls `add_stats`.
  - `hints_seen` is validated as an int from 0 to 20.
  - Failures are logged and never break the turn.
- **The snapshot** carries `stats`. Because the snapshot is sent before the write, the final turn's counts are added to the snapshot's `stats` in memory first, so the end screen includes the last turn.

## 4. The end screen

Shown in place of the action area when `game_over` is set. The final narration stays visible above it.

- **Heading:** `✦ VICTORY ✦` or `✦ YOUR TALE ENDS ✦`.
- **Quest summary,** from the snapshot:
  - name and archetype;
  - the ending: for victory, how Silo yielded, from the `ending` flag's value (might, wits or charm). For defeat, the line "Lord Silo's walls closed around you";
  - the seals won;
  - whether the Catalog was recovered.
- **What you just saw:** one line per non-zero stat, each with its glyph and a link that opens the Guide at the matching page.
  - The mapping: rolls and attacks → Tool calling; lore → Retrieval; memories → Memory; state commits → Game state; guardrails → Guardrails; hints → Hints.
  - If `since_start` is false, a small note says "counted from when this save was first played after the update".
- **What the realm will remember:** the snapshot's `distilled` entries. If there are none, it shows *"The Dreamer will remember this tale tonight."*
- **Buttons:** *Begin a new tale ▸*, *📖 Open the Guide*, and *open traces ↗* (the existing traces link).
- **Music:** the title theme, as today. No new tracks.

## 5. The Guide

- **Content:** `app/client/src/game/guide.ts` exports `GUIDE: GuidePage[]`, with `{id, glyph, title, saw, built, tryThis, docs}` per page.
  - **Pages:** `tools`, `rag`, `state`, `memory`, `structured`, `tracing`, `guardrails`, `evals`, `hints`.
  - `built` names the real pieces: for example `search_lore` → the AI Search `lore_index`; `rpg.quest_flags`, `rpg.adventure_stats`; the transcript store and the Dreamer; `dm_model` with `stay_in_sparkia`; `make eval` and `dm-evals`.
  - `tryThis` is the README "Things to try" row for that concept.
- **The overlay:** `Guide.tsx`, with a page list and the open page, closed with × or Escape.
  - It opens from a 📖 button on the title screen, a 📖 button in the game's right column, the end-screen lines, and a "More in the Guide ▸" link in each "(?)" explainer that has a matching page.
  - `EXPLAINERS` gains an optional `guide` page id.
- **README sync:**
  - a test reads `README.md` and checks that the "Things to try" table has a row for every page with a `tryThis`;
  - the README gets the new stats row: "finish an adventure, then `SELECT * FROM rpg.adventure_stats`".

## 6. Testing

- **Python:**
  - `next_hint`: act 1 order, the beat here preferred, act 2 seals in any order, act 3, and `None` at game over;
  - the content tests above;
  - `add_stats` and `stats` (in memory, and Postgres when the database is available, as the existing pgstore tests do), with `since_start` true on new adventures and false on saves from before M8;
  - the adapter: counts by event type, `hints_seen` validated, the final snapshot including the final turn, failures swallowed;
  - the snapshot carries `hint` and `stats`.
- **Front end (vitest):**
  - the hint reveal tiers and the close on a new turn;
  - `hints_seen` sent with the next turn and reset afterwards;
  - end-screen summary and recap lines built from a snapshot (pure functions);
  - the Guide page list;
  - the README sync test.
- **Live:**
  1. Deploy (`make db`, `deploy-agent`, `deploy-app`).
  2. Use a hint at the Inn.
  3. Play a short act, and `SELECT * FROM rpg.adventure_stats` shows the counts.
  4. Reach an ending via a seeded save, created with an `rpg.quest_flags` update on a test adventure. Then screenshot the end screen and the Guide.

## 7. Out of scope

- DM-narrated hints.
- New music.
- Backfilling stats for past turns.
- Achievements and badges.
- A Guide search.
