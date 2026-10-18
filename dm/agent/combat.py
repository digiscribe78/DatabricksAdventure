"""Declared attacks always roll: spot one in the player's words, and the note that nudges the DM.

The model sometimes narrates a swing without calling the combat tool, so the dice never decide it.
Code spots the declaration; the DM still chooses the target and may say there is no one to attack.
"""

import re

_VERBS = re.compile(
    r"\b(attack|attacks|attacking|strike|strikes|swing|swings|slash|slashes|stab|stabs|shoot|shoots|fire at|"
    r"blast|blasts|charge|charges|fight|fights|smite|smites|punch|kick|hack at|lunge at|cut down)\b"
)
# Everyday phrases that use a combat verb without attacking anyone.
_NOT_ATTACKS = re.compile(
    r"\bhit the road\b|\bfight (my|the) fear\b|\battack (the|this|that) (problem|question|puzzle)\b|"
    r"\b(about|of|on) the attack\b|\bstrike a (deal|bargain)\b|\bcharge (a|the) (fee|price)\b"
)

ATTACK_NUDGE = ("The player declared an attack. Call resolve_attack against the target before narrating; "
                "if there is no one to attack, say so in-world.")


def declares_attack(text: str) -> bool:
    t = (text or "").lower()
    return bool(_VERBS.search(t)) and not _NOT_ATTACKS.search(t)
