"""The story's rules (spec: docs/superpowers/specs/2026-10-17-campaign-design.md). Pure functions."""

from rpg.world import LOCATIONS

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

# Story beats per act, with where they can happen. Listed in "Story so far" only at their place and only
# while unrecorded: long-term memory ("you already swore that") would otherwise mask a missing flag.
BEATS: dict[int, list[tuple[str, str, str]]] = {
    1: [("vowed_to_find_aldric", "the player promises Marta to find Keeper Aldric", "medallion-inn"),
        ("knows_cellar_route", "optional, only if Marta's disposition is +2: she reveals the cellar route", "medallion-inn"),
        ("saw_the_diversion", "the Sweeper shows the older current of the night the river was diverted", "delta-crossing"),
        ("spoke_with_aldric", "Keeper Aldric speaks to the player through the Archive doors", "unity-archive")],
    2: [("seal_forge", "the player passes the Trial of Kindling by sharing the spark", "spark-forge"),
        ("forge_regret_shared", "optional: Ignatia confesses her forge made the fire for Silo's walls", "spark-forge"),
        ("seal_falls", "the player honestly faces a past choice at the Falls", "streaming-falls"),
        ("echo_saw_past_life", "optional: the Echo quotes a choice from another adventure", "streaming-falls"),
        ("seal_mines", "the player brings Odo's crew home", "photon-mines"),
        ("crew_rescued", "Odo's trapped crew is rescued", "photon-mines")],
    3: [("has_catalog", "the vault opens with all three seals and the player takes the Lost Catalog", "unity-archive"),
        ("aldric_forgives_silo", "optional: Aldric makes peace with his past and with Silo", "unity-archive"),
        ("grisle_outcome", "the player gets past Warden Grisle (fought, bribed or bluffed)", "data-swamp"),
        ("silo_wounds", "each successful attack on Lord Silo (1, 2, 3)", "silos-keep"),
        ("ending", "Lord Silo yields (might, wits or charm)", "silos-keep")],
}
# Where each story flag may be recorded: the bible's hard rules, enforced in code (spec §7.3).
FLAG_HOMES = {flag: where for beats in BEATS.values() for flag, _, where in beats}
AFTER_CATALOG = ("aldric_forgives_silo", "grisle_outcome", "silo_wounds", "ending")

_SEAL_NAMES = {"seal_forge": "Forge", "seal_falls": "Falls", "seal_mines": "Mines"}


def validate_flag(flag: str, value: str, flags: dict | None = None) -> str | None:
    if flag in CODE_FLAGS:
        return f"{flag} is set by the realm itself, not by the storyteller"
    if flag not in CANONICAL_FLAGS:
        # Only this act's beats: the error reaches the model, and later acts' flags would spoil the story.
        names = ", ".join(f for f, _, _ in BEATS[act(flags or {})])
        return f"unknown story flag {flag}; this act's story flags are: {names}"
    allowed = CANONICAL_FLAGS[flag]
    if allowed and value not in allowed:
        return f"{flag} must be one of {', '.join(allowed)}"
    return None


def check_flag(flag: str, value: str, flags: dict, location_id: str) -> str | None:
    """Story prerequisites for recording a flag here and now; None if allowed."""
    home = FLAG_HOMES.get(flag)
    if home and location_id != home:
        return f"{flag} can only be recorded at {LOCATIONS[home].name}"
    if flag == "has_catalog" and not all(flags.get(s) == "yes" for s in SEALS):
        return "the vault needs all three seals"
    if flag in AFTER_CATALOG and flags.get("has_catalog") != "yes":
        return f"{flag} cannot happen before the Lost Catalog is taken"
    if flag == "silo_wounds" and int(value) != int(flags.get("silo_wounds", "0")) + 1:
        return "Lord Silo's wounds count up one at a time"
    return None


def _yes(flags: dict, name: str) -> bool:
    return flags.get(name) == "yes"


def act(flags: dict) -> int:
    if _yes(flags, "has_catalog") or all(_yes(flags, s) for s in SEALS):
        return 3
    return 2 if _yes(flags, "spoke_with_aldric") else 1


def story_so_far(flags: dict, location_id: str) -> str:
    if outcome := game_over(flags):
        return f"The adventure has ended in {outcome}. Narrate only the epilogue; change nothing and call no tools."
    beats = [f"{flag}: {when}" for flag, when, where in BEATS[act(flags)] if flag not in flags and where == location_id]
    if not beats:
        return _progress(flags, location_id)
    return (f"{_progress(flags, location_id)} Record these story beats with set_quest_flag the moment they "
            f"happen; this adventure has not recorded them yet: {'; '.join(beats)}.")


def _progress(flags: dict, location_id: str) -> str:
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
    dcs = finale_dcs(flags)
    charm = f"Charm DC {dcs['charm']}" if dcs["charm"] else "Charm: not yet possible (Aldric has not forgiven Silo)"
    return (f"Finale: confront Lord Silo. Might: wound him three times (wounds {wounds}/3; set silo_wounds after each hit). "
            f"Wits: present the Catalog's proof, Wits DC {dcs['wits']}. {charm}. Roll the check at that DC; "
            "when he yields, the realm records the ending itself, so narrate it and do not set ending.")


def finale_dcs(flags: dict) -> dict:
    """The Wits and Charm difficulties to make Lord Silo yield (Charm is None until Aldric forgives him)."""
    wits = 12 if _yes(flags, "forge_regret_shared") else 16
    charm = None
    if _yes(flags, "aldric_forgives_silo"):
        charm = 12 if (_yes(flags, "marta_trusts_you") or _yes(flags, "echo_saw_past_life")) else 16
    return {"wits": wits, "charm": charm}


def finale_ending(flags: dict, location_id: str, rolls: list[dict]) -> str | None:
    """The ending a turn's dice earned in Silo's Keep: a Wits or Charm success at the finale's DC, else None.

    Code decides, like the Might path (the third wound) and defeat, so the ending never depends on the
    model remembering to set a flag.
    """
    if location_id != "silos-keep" or not _yes(flags, "has_catalog") or game_over(flags):
        return None
    dcs = finale_dcs(flags)
    for r in rolls:
        need = dcs.get(r.get("stat"))
        if need is not None and r.get("success") and int(r.get("dc", 0)) >= need:
            return r["stat"]
    return None


def game_over(flags: dict) -> str | None:
    if _yes(flags, "defeated_by_silo"):
        return "defeat"
    return "victory" if flags.get("ending") in CANONICAL_FLAGS["ending"] else None
