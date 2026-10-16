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
