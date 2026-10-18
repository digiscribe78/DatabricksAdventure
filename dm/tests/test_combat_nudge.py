"""A declared attack always rolls: the graph nudges the DM once if it narrates a swing without dice."""

from agent.combat import ATTACK_NUDGE, declares_attack
from agent.tools.dice import resolve_attack, roll_check
from langchain_core.messages import AIMessage, SystemMessage

from tests.fakes import ScriptedModel
from tests.test_dm_graph import PROSE, make, run, tc

SWING = tc("resolve_attack", stat="might", target="swamp rat", target_defence=10, damage_die=6, damage_bonus=2)


def test_declared_attacks_are_spotted():
    for text in ("I draw my longsword and attack the Silenced Archivist.", "I swing at Lord Silo again!",
                 "I blast it with my ember wand", "Strike the rat", "I stab the wraith", "I charge the Warden"):
        assert declares_attack(text), text


def test_near_misses_are_not_attacks():
    for text in ("I hit the road to the Delta.", "I fight my fear and step onto the bridge.",
                 "Let me attack the problem from another angle.", "I ask Marta about the attack on the Archive.",
                 "I promise Marta I will find Keeper Aldric.", ""):
        assert not declares_attack(text), text


def nudged(calls):
    return [c for c in calls if any(isinstance(m, SystemMessage) and ATTACK_NUDGE in m.content for m in c)]


def test_a_swing_without_dice_is_nudged_once_and_rolls():
    model = ScriptedModel(replies=[AIMessage(content="You swing wide."), AIMessage(content="", tool_calls=[SWING]),
                                   AIMessage(content="draft")], structured=[PROSE])
    turn = run(make(model, [resolve_attack, roll_check]), "I attack the swamp rat with my longsword.")["turn"]
    assert [e["type"] for e in turn["events"]] == ["attack"]
    assert len(nudged(model.reason_calls)) == 1


def test_the_nudge_never_repeats_in_a_turn():
    model = ScriptedModel(replies=[AIMessage(content="You swing wide."), AIMessage(content="There is no one here to fight.")],
                          structured=[PROSE])
    turn = run(make(model, [resolve_attack]), "I attack the shadows.")["turn"]
    assert turn["narration"] == PROSE.narration and len(model.reason_calls) == 2


def test_turns_that_rolled_or_are_not_attacks_are_left_alone():
    rolled = ScriptedModel(replies=[AIMessage(content="", tool_calls=[SWING]), AIMessage(content="draft")], structured=[PROSE])
    run(make(rolled, [resolve_attack]), "I attack the swamp rat.")
    talk = ScriptedModel(replies=[AIMessage(content="Marta smiles.")], structured=[PROSE])
    run(make(talk, [resolve_attack]), "I ask Marta about the river.")
    assert not nudged(rolled.reason_calls) and not nudged(talk.reason_calls)
