import json

import pytest
from devtools.guardrails_check import report
from devtools.model_service import create_body, ensure_model_service, service_name
from langchain_core.messages import AIMessage


def test_service_name_lives_in_the_game_schema():
    assert service_name("cat", "sch") == "cat.sch.dm_model"


def test_dm_model_routes_only_to_sonnet():
    [dest] = create_body()["config"]["routing"]["destinations"]
    assert dest["name"] == "system.ai.databricks-claude-sonnet-4-5"
    assert dest["destination_type"] == "DESTINATION_TYPE_PAY_PER_TOKEN_FOUNDATION_MODEL"
    assert dest["traffic_percentage"] == 100


def test_existing_service_is_left_alone():
    calls = []
    assert ensure_model_service("p", "cat", "sch", run=lambda cmd: calls.append(cmd)) is False
    assert [c[2] for c in calls] == ["get-model-service"]


def test_missing_service_is_created():
    calls = []

    def run(cmd):
        calls.append(cmd)
        if cmd[2] == "get-model-service":
            raise RuntimeError("databricks ai-gateway get-model-service failed: Error: Resource not found")

    assert ensure_model_service("p", "cat", "sch", run=run) is True
    create = calls[-1]
    assert create[2:5] == ["create-model-service", "schemas/cat.sch", "dm_model"]
    assert json.loads(create[create.index("--json") + 1]) == create_body()


def test_other_errors_are_not_mistaken_for_missing():
    def run(cmd):
        raise RuntimeError("databricks ai-gateway get-model-service failed: PERMISSION_DENIED")

    with pytest.raises(RuntimeError, match="PERMISSION_DENIED"):
        ensure_model_service("p", "cat", "sch", run=run)


def test_guardrails_check_reports_the_blocking_policy_or_warns():
    blocked = AIMessage(content="This request was blocked by the 'block_jailbreak' service policy.",
                        response_metadata={"finish_reason": "content_filter"})
    assert "block_jailbreak blocked" in report(blocked)
    assert report(AIMessage(content="Sure!")).startswith("WARNING")
