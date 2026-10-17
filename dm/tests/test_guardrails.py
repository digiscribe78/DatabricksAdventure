from agent.guardrails import (
    POLICY_LABELS,
    REFUSED_PLACEHOLDER,
    Block,
    blocked_by,
    guardrail_event,
    refusal_line,
)
from agent.prompts import REFUSAL_SYSTEM
from langchain_core.messages import AIMessage
from rpg.turn import ComposeOutput

BLOCK = AIMessage(content="This request was blocked by the 'block_jailbreak' service policy.",
                  response_metadata={"finish_reason": "content_filter"})


def test_a_gateway_block_names_its_policy():
    assert blocked_by(BLOCK) == Block("block_jailbreak")


def test_a_block_that_names_no_policy_is_unknown():
    msg = AIMessage(content="Blocked.", response_metadata={"finish_reason": "content_filter"})
    assert blocked_by(msg) == Block("unknown")


def test_normal_replies_and_tool_calls_are_not_blocks():
    assert blocked_by(AIMessage(content="The river runs fast.", response_metadata={"finish_reason": "stop"})) is None
    assert blocked_by(AIMessage(content="")) is None


def test_canned_refusals_are_valid_turn_narration():
    for policy in [*POLICY_LABELS, "unknown"]:
        line = refusal_line(policy)
        ComposeOutput(narration=line, choices=["a", "b"])  # validates
        assert 40 <= len(line.split()) <= 200
        for word in ("AI", "model", "policy", "prompt"):
            assert word not in line.split()


def test_guardrail_event_names_the_policy_and_what_it_does():
    e = guardrail_event("block_jailbreak")
    assert e.type == "guardrail" and e.detail == {"policy": "block_jailbreak"}
    assert e.summary == "Guardrail: block_jailbreak (jailbreak screen) refused this turn"
    assert guardrail_event("mystery").summary == "Guardrail: mystery refused this turn"


def test_refusal_prompt_names_the_place_and_never_the_words():
    text = REFUSAL_SYSTEM.format(place="The Medallion Inn")
    assert "The Medallion Inn" in text and "must not guess, repeat or mention" in text
    assert REFUSED_PLACEHOLDER.startswith("(") and "refused" in REFUSED_PLACEHOLDER
