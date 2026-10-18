import random
from pathlib import Path

import agent.tools.dice as dice
import pytest
from agent.dm_graph import FALLBACK_NARRATION, MAX_TOOL_CALLS_PER_TURN, build_dm_graph
from agent.tools.dice import roll_check
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from rpg.turn import ComposeOutput
from rpg.store import InMemoryStore, load_npc_cards
from rpg.world import START_LOCATION_ID

from tests.fakes import ScriptedModel

PROSE = ComposeOutput(narration="Marta eyes you over the bar.", choices=["Ask about the river", "Order ale"])


class FixedRng(random.Random):
    def __init__(self, v):
        super().__init__(0)
        self.v = v

    def randint(self, a, b):
        return self.v


@pytest.fixture(autouse=True)
def fixed_dice(monkeypatch):
    monkeypatch.setattr(dice, "RNG", FixedRng(15))


def call(name="roll_check", idx=0, **args):
    args = args or {"stat": "charm", "dc": 12, "reason": "haggle"}
    return {"name": name, "args": args, "id": f"call-{idx}", "type": "tool_call"}


def run(graph, content, thread="t1"):
    msgs = [] if content is None else [{"role": "user", "content": content}]
    return graph.invoke({"messages": msgs}, {"configurable": {"thread_id": thread}})


NPCS = Path(__file__).resolve().parents[2] / "content" / "npcs"


def new_store(sid="t1"):
    s = InMemoryStore(load_npc_cards(NPCS))
    s.create_adventure(sid, "player-1", "Brannoc", "warrior")
    return s


def make(model, tools=None, store=None):
    return build_dm_graph(model, tools or [roll_check], checkpointer=InMemorySaver(),
                          store=store if store is not None else new_store())


def test_plain_turn_returns_valid_turn_output():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    out = run(make(model), "I look around.")
    turn = out["turn"]
    assert turn["narration"] == PROSE.narration
    assert turn["choices"] == PROSE.choices
    assert turn["location_id"] == START_LOCATION_ID
    assert turn["events"] == []
    assert isinstance(out["messages"][-1], AIMessage)


def test_tool_roll_becomes_code_built_event():
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[call()]), AIMessage(content="done")],
        structured=[PROSE],
    )
    turn = run(make(model), "I haggle with Marta.")["turn"]
    assert len(turn["events"]) == 1
    ev = turn["events"][0]
    assert ev["type"] == "roll"
    assert ev["detail"]["total"] == 16  # 15 + Warrior charm +1
    assert "15" in ev["summary"] and "16" in ev["summary"] and "DC 12" in ev["summary"]


def test_dm_system_prompt_includes_character_and_location():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    run(make(model), "Hello")
    system = model.reason_calls[0][0]
    assert isinstance(system, SystemMessage)
    assert "Brannoc" in system.content and "Medallion Inn" in system.content


def test_tool_budget_stops_runaway_loop_and_drops_unanswered_call():
    looping = [AIMessage(content="", tool_calls=[call(idx=i)]) for i in range(MAX_TOOL_CALLS_PER_TURN + 1)]
    model = ScriptedModel(replies=looping, structured=[PROSE])
    out = run(make(model), "I keep rolling.")
    compose_input = model.structured_calls[0]
    tool_msgs = [m for m in compose_input if isinstance(m, ToolMessage)]  # saved history is compacted
    assert len(tool_msgs) == MAX_TOOL_CALLS_PER_TURN
    last_non_system = [m for m in compose_input if not isinstance(m, SystemMessage)][-1]
    assert not getattr(last_non_system, "tool_calls", None)
    assert len(out["turn"]["events"]) == MAX_TOOL_CALLS_PER_TURN


def test_bad_tool_args_do_not_crash_turn():
    bad = call(stat="strength", dc=12, reason="x")
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[bad]), AIMessage(content="done")],
        structured=[PROSE],
    )
    out = run(make(model), "I flex.")
    assert out["turn"]["narration"] == PROSE.narration
    assert out["turn"]["events"] == []


def test_structured_output_retries_once_then_succeeds():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[ValueError("bad json"), PROSE])
    turn = run(make(model), "Hi")["turn"]
    assert turn["narration"] == PROSE.narration
    assert len(model.structured_calls) == 2


def test_structured_output_double_failure_gives_fallback_turn():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[ValueError("x"), ValueError("y")])
    turn = run(make(model), "Hi")["turn"]
    assert turn["narration"] == FALLBACK_NARRATION
    assert 2 <= len(turn["choices"]) <= 4


def test_fallback_reuses_previous_choices():
    model = ScriptedModel(
        replies=[AIMessage(content="ok"), AIMessage(content="ok")],
        structured=[PROSE, ValueError("x"), ValueError("y")],
    )
    graph = make(model)
    run(graph, "Hi")
    turn = run(graph, "Again")["turn"]
    assert turn["choices"] == PROSE.choices


def test_empty_first_invocation_sets_opening_scene():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    run(make(model), None)
    sent = model.reason_calls[0]
    assert isinstance(sent[-1], HumanMessage)


def test_state_persists_across_turns_in_a_session():
    model = ScriptedModel(
        replies=[AIMessage(content="ok"), AIMessage(content="ok")], structured=[PROSE, PROSE]
    )
    graph = make(model)
    first = run(graph, "Hi")
    second = run(graph, "Hello again")
    assert second["character"] == first["character"]
    assert second["location_id"] == START_LOCATION_ID
    humans = [m for m in second["messages"] if isinstance(m, HumanMessage)]
    assert [h.content for h in humans] == ["Hi", "Hello again"]


def test_budget_exhaustion_leaves_valid_history_for_next_turn():
    looping = [AIMessage(content="", tool_calls=[call(idx=i)]) for i in range(MAX_TOOL_CALLS_PER_TURN + 1)]
    model = ScriptedModel(replies=[*looping, AIMessage(content="ok")], structured=[PROSE, PROSE])
    graph = make(model)
    run(graph, "I keep rolling.")
    turn = run(graph, "Now I stop.")["turn"]  # the fake fails like a provider on an orphan tool_use
    assert turn["narration"] == PROSE.narration


def test_parallel_calls_crossing_budget_leave_valid_history():
    first = AIMessage(content="", tool_calls=[call(idx=i) for i in range(5)])
    over = AIMessage(content="", tool_calls=[call(idx=10), call(idx=11)])
    model = ScriptedModel(replies=[first, over, AIMessage(content="ok")], structured=[PROSE, PROSE])
    graph = make(model)
    run(graph, "Roll everything.")
    assert run(graph, "Next.")["turn"]["narration"] == PROSE.narration


def test_one_assistant_message_per_turn_in_history():
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[call()]), AIMessage(content="hidden draft prose")],
        structured=[PROSE],
    )
    out = run(make(model), "I haggle.")
    prose = [m for m in out["messages"] if isinstance(m, AIMessage) and not m.tool_calls]
    assert len(prose) == 1
    assert "hidden draft prose" not in prose[0].content


def test_reason_model_error_gives_in_world_fallback():
    model = ScriptedModel(replies=[RuntimeError("gateway 429")], structured=[])
    turn = run(make(model), "Hi")["turn"]
    assert turn["narration"] == FALLBACK_NARRATION
    assert model.structured_calls == []  # no second model call after a failed reason step


def test_lore_tool_result_becomes_lore_event(monkeypatch):
    import agent.tools.lore as lore
    from agent.tools.lore import search_lore

    passage = {"text": "t", "source": "delta-crossing", "page": 1, "doc_type": "location", "location_id": "delta-crossing"}
    monkeypatch.setattr(lore, "SEARCH", lambda q, s: [passage])
    lore_call = {"name": "search_lore", "args": {"query": "the river"}, "id": "lore-0", "type": "tool_call"}
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[lore_call]), AIMessage(content="draft")],
        structured=[PROSE],
    )
    graph = make(model, [roll_check, search_lore])
    events = run(graph, "Tell me about the river.")["turn"]["events"]
    assert [e["type"] for e in events] == ["lore"]
    assert events[0]["summary"] == "Lore: 1 passages for 'the river' (delta-crossing)"
    assert events[0]["detail"]["passages"] == [passage]


def test_failed_lore_lookup_still_completes_turn(monkeypatch):
    import agent.tools.lore as lore
    from agent.tools.lore import search_lore

    def boom(q, s):
        raise RuntimeError("down")

    monkeypatch.setattr(lore, "SEARCH", boom)
    lore_call = {"name": "search_lore", "args": {"query": "x"}, "id": "lore-0", "type": "tool_call"}
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[lore_call]), AIMessage(content="draft")],
        structured=[PROSE],
    )
    graph = make(model, [roll_check, search_lore])
    turn = run(graph, "Tell me a legend.")["turn"]
    assert turn["narration"] == PROSE.narration
    assert [e["type"] for e in turn["events"]] == ["warning"]  # visible, never silent


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


def test_reload_failure_after_successful_commit_is_not_reported_as_failure():
    class FlakyReload(InMemoryStore):
        loads = 0

        def load(self, sid):
            FlakyReload.loads += 1
            if FlakyReload.loads == 2:  # 1st = load_state, 2nd = reload after commit
                raise ConnectionError("blip")
            return super().load(sid)

    store = FlakyReload(load_npc_cards(NPCS))
    store.create_adventure("t1", "p", "Brannoc", "warrior")
    FlakyReload.loads = 0
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[tc("update_character", gold_delta=-2, items_add=["lantern"])]),
                 AIMessage(content="d")],
        structured=[PROSE],
    )
    turn = run(make(model, STATE_TOOLS, store), "I buy a lantern.")["turn"]
    assert turn["narration"] == PROSE.narration
    assert turn["events"][-1]["type"] == "state"
    assert store.load("t1").character.gold == 10


def test_reason_failure_after_staged_change_commits_nothing():
    store = new_store()
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[tc("update_character", gold_delta=-2)]), RuntimeError("429"),
                 AIMessage(content="ok")],
        structured=[PROSE],
    )
    graph = make(model, STATE_TOOLS, store)
    turn = run(graph, "I pay.")["turn"]
    assert turn["narration"] == FALLBACK_NARRATION and turn["events"] == []
    assert store.load("t1").character.gold == 12
    run(graph, "Again.")
    assert not any(isinstance(m, ToolMessage) for m in model.reason_calls[-1])


def test_compose_is_told_what_state_was_applied():
    store = new_store()
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[tc("update_character", hp_delta=-30)]), AIMessage(content="d")],
        structured=[PROSE],
    )
    run(make(model, STATE_TOOLS, store), "I leap off the bridge.")
    compose_system = model.structured_calls[0][0].content
    assert "downed" in compose_system and "HP 18 → 0" in compose_system


def test_turn_for_another_players_adventure_is_refused():
    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    graph = make(model)
    with pytest.raises(PermissionError):
        graph.invoke({"messages": [{"role": "user", "content": "hi"}]},
                     {"configurable": {"thread_id": "t1", "actor_id": "someone-else"}})


from agent.dm_graph import HISTORY_TURNS


def test_finished_turn_is_compacted_to_player_and_narration():
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[call()]), AIMessage(content="draft")], structured=[PROSE]
    )
    out = run(make(model), "I haggle with Marta.")
    assert [type(m).__name__ for m in out["messages"]] == ["HumanMessage", "AIMessage"]
    assert not out["messages"][-1].tool_calls
    assert out["turn"]["events"][0]["type"] == "roll"  # events still built from the tool results


def test_current_turn_keeps_its_tool_results_while_reasoning():
    model = ScriptedModel(
        replies=[AIMessage(content="", tool_calls=[call()]), AIMessage(content="draft")], structured=[PROSE]
    )
    run(make(model), "I haggle with Marta.")
    second_reason_input = model.reason_calls[1]
    assert any(isinstance(m, ToolMessage) for m in second_reason_input)


def test_model_sees_at_most_history_turns_past_turns():
    turns = HISTORY_TURNS + 3
    model = ScriptedModel(replies=[AIMessage(content="ok")] * turns, structured=[PROSE] * turns)
    graph = make(model)
    for i in range(turns):
        run(graph, f"turn {i}")
    for sent in (model.reason_calls[-1], model.structured_calls[-1]):
        # compose ends with its own short cue (some models refuse assistant prefill); it isn't a turn
        humans = [m.content for m in sent if isinstance(m, HumanMessage) and not m.content.startswith("(Now write")]
        assert len(humans) == HISTORY_TURNS + 1
        assert humans[-1] == f"turn {turns - 1}"


def test_first_turn_recalls_memories_once_and_emits_event():
    asked = []

    def recall(actor):
        asked.append(actor)
        return ["Spared the thief in the swamp"]

    model = ScriptedModel(replies=[AIMessage(content="ok"), AIMessage(content="ok")], structured=[PROSE, PROSE])
    graph = build_dm_graph(model, [roll_check], checkpointer=InMemorySaver(), store=new_store(), recall=recall)
    cfg = {"configurable": {"thread_id": "t1", "actor_id": "player-1"}}
    first = graph.invoke({"messages": []}, cfg)["turn"]
    second = graph.invoke({"messages": [{"role": "user", "content": "hi"}]}, cfg)["turn"]
    assert asked == ["player-1"]
    assert first["events"][0]["type"] == "memory" and "1 thing" in first["events"][0]["summary"]
    assert [e["type"] for e in second["events"]] == []
    assert "Spared the thief in the swamp" in model.reason_calls[-1][0].content


def test_memory_outage_does_not_break_the_turn():
    def recall(actor):
        raise ConnectionError("memory store down")

    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    graph = build_dm_graph(model, [roll_check], checkpointer=InMemorySaver(), store=new_store(), recall=recall)
    turn = graph.invoke({"messages": []}, {"configurable": {"thread_id": "t1", "actor_id": "player-1"}})["turn"]
    assert turn["narration"] == PROSE.narration and turn["events"] == []


def test_slow_memory_recall_is_abandoned_within_budget(monkeypatch):
    import time

    import agent.dm_graph as g

    monkeypatch.setattr(g, "RECALL_TIMEOUT_S", 0.2)

    def slow(actor):
        time.sleep(3)
        return ["too late"]

    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    graph = build_dm_graph(model, [roll_check], checkpointer=InMemorySaver(), store=new_store(), recall=slow)
    started = time.monotonic()
    turn = graph.invoke({"messages": []}, {"configurable": {"thread_id": "t1", "actor_id": "player-1"}})["turn"]
    assert time.monotonic() - started < 2
    assert turn["events"] == []


def test_resuming_without_a_message_uses_the_continue_cue_not_the_opening():
    from agent.prompts import CONTINUE_CUE, OPENING_CUE

    model = ScriptedModel(replies=[AIMessage(content="ok"), AIMessage(content="ok")], structured=[PROSE, PROSE])
    graph = make(model)
    run(graph, None)          # new game: opening
    run(graph, None)          # Continue: resume
    first, second = model.reason_calls[0], model.reason_calls[1]
    assert first[-1].content == OPENING_CUE
    assert second[-1].content == CONTINUE_CUE


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


def test_aldric_secret_is_hidden_until_act_three():
    from rpg.state import NpcCard

    aldric = NpcCard(npc_id="keeper-aldric", name="Keeper Aldric", persona="p", speech_style="s",
                     secrets="Lord Silo was his master.", home_location_id="unity-archive", reveal_after="has_catalog")
    for flags, visible in [({"spoke_with_aldric": "yes"}, False), ({"has_catalog": "yes"}, True)]:
        store = InMemoryStore([aldric])
        store.create_adventure("t1", "p", "Brannoc", "warrior")
        game = store.load("t1")
        game.location_id = "unity-archive"
        game.flags.update(flags)
        store.commit("t1", game)
        model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
        run(make(model, store=store), "Who is Silo to you?")
        system = model.reason_calls[0][0].content
        assert ("Lord Silo was his master" in system) is visible
        assert "Never reveal" in system  # bible DM rules live in the system prompt, not only in lore
