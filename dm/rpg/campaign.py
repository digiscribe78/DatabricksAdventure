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
