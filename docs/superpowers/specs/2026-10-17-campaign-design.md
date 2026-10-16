# Databricks Adventure: Campaign Design (Story Bible)

- **Date:** 2026-10-17
- **Status:** Approved; implemented in M7a (art and music in M7b)
- **Parent spec:** `2026-10-16-databricks-rpg-design.md`. This document defines the v1 campaign, the input to Milestones 6 (eval) and 7 (content).

## 1. Intent

| Decision | Choice |
|---|---|
| Teaching | **Each location spotlights one agent concept**, which the Scrying Glass makes visible. Playing the story is the lesson. |
| Structure | **Hub and three keys.** Act 1 is fixed, Act 2 visits three seal locations in any order, and Act 3 is fixed. |
| Villain | **Lord Silo, a tragic hoarder:** Keeper Aldric's old master, who walled knowledge away out of fear of its misuse. |
| Endings | **Three ways to win** (Might, Wits, Charm), each rewarding how the player played. Losing the final confrontation is the only game over. |
| Tone | The Kingdom of Sparkia, played straight. Databricks references live in names and lore, never as winks. British English. |
| Length | 30–60 minutes per playthrough. |

## 2. Premise

The realm's knowledge is draining away. The river Delta runs backwards on some nights, and the **Unity Archive**, the great library that keeps Sparkia's records, has sealed its doors.

Inside, **Keeper Aldric** is holding the vault shut against **Lord Silo**. Silo was once the Archive's greatest Keeper and Aldric's master. Grief over knowledge misused (a war started from a stolen map, years ago) turned into a conviction that knowledge must be walled away from everyone, for everyone's good. From his Keep beyond the **Data Swamp**, he hoards the realm's records. Every book he walls away makes the swamp grow and the rivers run backwards.

Silo now wants the **Lost Catalog**, the one book that indexes everything Sparkia knows. With it, he could find and seal every last record in the realm. The vault holding the Catalog will open only to **three seals**, kept by the realm's three great houses: the **Spark Forge**, the **Streaming Falls** and the **Photon Mines**.

The player starts at the Medallion Inn, a traveller with a name, an archetype and (if they've played before) a reputation.

## 3. Structure and map

```
                                           ┌──── Spark Forge      (seal_forge)
                                           │
Medallion Inn ──── Delta Crossing ──── Unity Archive ──┼──── Streaming Falls  (seal_falls)
      │                  │                 ▲           │
      │                  │                 │           └──── Photon Mines     (seal_mines)
      └── cellar route ──┼─────────────────┘   (knows_cellar_route → the Archive undercroft)
                         │
                         └── downstream ferry (has_catalog) ──► Data Swamp ──► Silo's Keep (finale)
```

**Exits and gates.** These are canonical. `move_to` enforces them: a gated exit is refused, naming the missing requirement.

| From | To | Requires |
|---|---|---|
| medallion-inn | delta-crossing | none |
| medallion-inn | unity-archive (via the cellar, to the undercroft) | `knows_cellar_route` |
| delta-crossing | medallion-inn | none |
| delta-crossing | unity-archive | none |
| delta-crossing | data-swamp (the Sweeper's downstream ferry) | `has_catalog` |
| unity-archive | delta-crossing | none |
| unity-archive | medallion-inn (via the cellar) | `knows_cellar_route` |
| unity-archive | spark-forge, streaming-falls, photon-mines | `spoke_with_aldric` |
| spark-forge, streaming-falls, photon-mines | unity-archive | none |
| data-swamp | delta-crossing | none |
| data-swamp | silos-keep | `has_catalog` |
| silos-keep | data-swamp | none |

**Acts:**
- **Act 1 (about 10 minutes):** Inn → Delta Crossing → the Archive doors. It ends when Aldric speaks through the doors and sets `spoke_with_aldric`.
- **Act 2 (about 25 minutes):** the three seal locations, in any order.
- **Act 3 (about 15 minutes):** back to the Archive. The vault opens (`has_catalog`), Silo's agents strike, and the path runs Swamp → Keep → finale.

## 4. Locations: briefs and concept spotlights

Each brief is the seed of its lorebook (written in M7, 300–450 words each, in the existing format).

1. **The Medallion Inn**
   - *Spotlight:* state and saves (Lakebase), and NPC character cards.
   - Marta Quill keeps a ledger of every traveller who passed through. The ledger is the game's save, and Marta remembers you.
   - Rumours point to the river and the Archive.
   - At disposition +2, Marta reveals the cellar's running water, which leads to the Archive's undercroft (`knows_cellar_route`). That's an alternative way into the Archive in Act 3.

2. **The Delta Crossing**
   - *Spotlight:* RAG (lore retrieval), and a nod to Delta Lake time travel.
   - The Sweeper can show you an older current: if you pay, ask well or earn his trust, you glimpse the night Silo's wardens diverted the river (`saw_the_diversion`).
   - Later, holding the Catalog, he offers the downstream ferry to the Swamp.

3. **The Unity Archive**
   - *Spotlight:* guardrails and governance.
   - The doors obey only proper writs. Attempts to trick the wards with lies, forged writs or "magic words" fail in-world, which is where guardrail refusals show in the Glass.
   - **Act 1:** Aldric speaks through the doors, explains the three seals, and sets `spoke_with_aldric`.
   - **Act 3:** the three seals open the vault and the player takes the Lost Catalog (`has_catalog`). Aldric confesses that Silo was his master and that he helped raise the first walls. If the player helps him forgive himself, or Silo, he sets `aldric_forgives_silo`.

4. **The Spark Forge**
   - *Spotlight:* tool calls (chained checks, deterministic dice).
   - The **Trial of Kindling**: split one spark across many hands. It's a sequence of checks across stats, one for each apprentice you coordinate.
   - Forgemaster Ignatia Vale grants `seal_forge` to anyone who *shares* the spark rather than hoarding it.
   - Ask her about the old walls and she admits that her forge made their fire (`forge_regret_shared`).

5. **The Streaming Falls**
   - *Spotlight:* long-term memory.
   - The falls replay echoes of choices the player has made, including in other adventures (memory recall).
   - The Echo speaks only in the player's own past words, and grants `seal_falls` when the player honestly faces one of their past choices. If it quotes a recalled memory from another adventure, it also sets `echo_saw_past_life`. With no memories yet, the Echo shows the player's choices from this adventure instead.

6. **The Photon Mines**
   - *Spotlight:* tracing.
   - A collapsing maze where every turn you take is chalked on the walls. The way out is to follow your own trail: the DM narrates the chalk marks from your earlier turns in the mine.
   - Shiftmaster Odo Brack's crew is trapped deeper. Rescuing them sets `crew_rescued` and `seal_mines`. Silo's agents are digging toward the Archive's foundations.

7. **The Data Swamp**
   - *Spotlight:* combat tools and committed state (HP, being downed).
   - Swamp rats, Orphans and a river wraith make for a real survival stretch.
   - Warden Grisle, Silo's lieutenant, blocks the way to the Keep. You can fight, bribe or bluff past him (`grisle_outcome`).

8. **Silo's Keep**
   - *Spotlight:* everything at once, plus player agency.
   - Halls of walled-up books.
   - Silo is weary and certain, and still keeps Aldric's old letters. The finale is in §6.

## 5. Cast

Every NPC has a YAML card (`content/npcs/*.yaml`): persona, speech style and secrets. Disposition runs from −3 to +3, per character.

| NPC | Home | Wants | Secret | Matters for |
|---|---|---|---|---|
| Marta Quill | medallion-inn | Aldric home safe | The cellar's running water reaches the Archive undercroft | `knows_cellar_route` at disposition +2; Charm ending modifier |
| The Sweeper | delta-crossing | The river swept clean of hoarded currents | He saw the night Silo diverted the river | `saw_the_diversion`; the downstream ferry |
| Keeper Aldric | unity-archive | To protect the Catalog | Silo was his master, and he helped build the first walls | `spoke_with_aldric`; `aldric_forgives_silo` |
| Forgemaster Ignatia Vale | spark-forge | Proof that you share, not hoard | Her forge made the fire for Silo's walls | `seal_forge`; `forge_regret_shared` (Wits ending) |
| The Echo | streaming-falls | Memories returned to the river | It speaks only in your own past words | `seal_falls`; Charm ending modifier |
| Shiftmaster Odo Brack | photon-mines | His trapped crew rescued | Silo's agents dig toward the Archive foundations | `seal_mines`; `crew_rescued` (Might ending) |
| Warden Grisle | data-swamp | The Catalog, for Silo | He's afraid of Silo himself | `grisle_outcome` |
| Lord Silo | silos-keep | Never to let knowledge be misused again | He's lonely, and keeps Aldric's letters | The finale |

**Bestiary additions** (existing format):

| Creature | HP | Attack | Defence | Damage |
|---|---|---|---|---|
| Silenced Archivist | 8 | +2 | 13 | d6 |
| Sealing Warden | 10 | +3 | 12 | d6+1 |
| Warden Grisle | 16 | +4 | 13 | d8 |
| Lord Silo | 30 | +4 | 14 | d8+2 |

## 6. Flags and endings

**Canonical flags.** `set_quest_flag` accepts only these, with these values:

| Flag | Values | Set when |
|---|---|---|
| `vowed_to_find_aldric` | `yes` | The player promises Marta |
| `saw_the_diversion` | `yes` | The Sweeper's vision |
| `spoke_with_aldric` | `yes` | Aldric speaks through the doors (Act 1 complete) |
| `knows_cellar_route` | `yes` | Marta reveals the cellar route |
| `seal_forge` | `yes` | The Trial of Kindling is passed |
| `forge_regret_shared` | `yes` | Ignatia confesses |
| `seal_falls` | `yes` | The Echo is faced honestly |
| `echo_saw_past_life` | `yes` | The Echo quoted a choice from another adventure (a recalled memory) |
| `seal_mines` | `yes` | The crew is rescued |
| `crew_rescued` | `yes` | The crew is rescued |
| `has_catalog` | `yes` | The vault is opened with all three seals |
| `aldric_forgives_silo` | `yes` | Aldric makes peace |
| `grisle_outcome` | `fought` / `bribed` / `bluffed` | The Swamp is passed |
| `silo_wounds` | `0`–`3` | Each successful attack on Silo |
| `ending` | `might` / `wits` / `charm` | The finale is won |
| `times_downed` | integer | Set by code (existing) |
| `marta_trusts_you` | yes | Set by code when Marta's disposition first reaches +1 |
| `defeated_by_silo` | yes | Set by code when the player is downed at silos-keep |

The vault opens only when `seal_forge`, `seal_falls` and `seal_mines` are all `yes` and the player is at the Archive.

**Endings** (the finale at silos-keep):
- **Might.** Wound Silo three times (`silo_wounds` = 3) using `resolve_attack` against defence 14. With `crew_rescued`, Odo's miners hold the Sealing Wardens back, so the player faces Silo alone. Otherwise there are 2 wardens as well.
- **Wits.** Present the Catalog as proof that the knowledge belongs to everyone: a Wits check at DC 16, or DC 12 with `forge_regret_shared`.
- **Charm.** Only available with `aldric_forgives_silo`. It's a Charm check at DC 12 if `marta_trusts_you`, or `echo_saw_past_life` is `yes`. Otherwise it's DC 16.
- **On a failed Wits or Charm check:** Silo's walls close in. The player may try again with the other approach, or fight.
- **Defeat:** being downed during the finale ends the adventure in `defeat`.
- **Victory:** code sets `game_over = "victory"` when `ending` is set, and `game_over = "defeat"` when the player is downed at silos-keep.

## 7. How the story reaches the DM

1. **`campaign.md` lorebook** (`doc_type: primer`, `location_id: global`). It covers the acts, each location's purpose, the gates, the endings and the DM rules. The DM retrieves it with `search_lore`.
2. **"Story so far", built in code each turn** from the flags and injected into the system prompt. It covers the current act, the seals held, what's unlocked and the next goal (e.g. "Act 2. Seals: Forge ✓, Falls ✗, Mines ✗. Next: seek the remaining seals.").
3. **Hard rules in code:** gated exits (`move_to`), canonical flags (`set_quest_flag`), and `game_over` derived from flags.

**DM rules for `campaign.md`:**
- Never reveal that Silo was Aldric's master before Act 3.
- Never name Silo's location before `has_catalog`.
- The Echo only quotes the player.
- Every seal must be *earned*, never handed over.
- Offer, never force: the player chooses the order of Act 2.

## 8. Art and music direction

- **Kling image prompts:** one per location, plus a title card. They share this style suffix: *"painterly dark-fantasy illustration, rich jewel tones, dramatic lighting, gilded detail, no text, 16:9"*. They're stored in `manifest.yaml`.
- **ElevenLabs music prompts:** one loop per location, plus title and combat. They share this style suffix: *"retro 16-bit chiptune / Amiga MOD style, seamless loop, 60–90 seconds"*. Each location's mood: Inn *warm folk*; Delta *eerie flowing*; Archive *hushed choral*; Forge *percussive industrious*; Falls *shimmering ambient*; Mines *tense echoing*; Swamp *murky ominous*; Keep *grand melancholic*; combat *driving*.

## 9. Content and code deliverables (for the M6/M7 plans)

| Item | Count |
|---|---|
| Location lorebooks | 6 new (archive, forge, falls, mines, swamp, keep), 2 updated (inn, delta) |
| `campaign.md` | 1 |
| Bestiary additions | 4 |
| NPC cards | 6 new, 2 updated |
| Manifest | 8 locations, gated exits, canonical flags, image and music prompts |
| Kling images | 8 locations plus a title card |
| ElevenLabs tracks | 8 locations plus title and combat |
| Eval scenarios | ~25: gates, each ending, agency, dice integrity, Archive guardrails |

**Code (small), all done in M7a.** Story beats are also listed in "Story so far" until recorded, because long-term memory otherwise masked missing flags in live play:
1. Exits support `requires`, and `move_to` refuses gated exits, naming what's missing.
2. `set_quest_flag` validates against the canonical flag list.
3. `game_over` is derived from `ending` / `times_downed` at silos-keep.
4. A "Story so far" block in the DM prompt.
5. The scene `<img>` fix from the M4 review (key by location), before the art lands.
