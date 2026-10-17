import math

import pandas as pd
from evals.run import summarise, to_dataset
from evals.scenarios import Scenario


def test_dataset_rows_carry_inputs_and_only_set_expectations():
    s = Scenario.model_validate({"id": "a", "category": "lore", "state": {"location_id": "unity-archive"},
                                 "input": "What are the seals?", "expect": {"tools": ["search_lore"]}})
    assert to_dataset([s]) == [{"inputs": {"scenario_id": "a", "player_input": "What are the seals?"},
                                "expectations": {"tools": ["search_lore"]}}]


def test_summary_counts_passes_skips_na_and_ignores_expectation_columns():
    df = pd.DataFrame([
        {"request": {"scenario_id": "a"}, "tool_selection/value": True, "tool_selection/rationale": "ok",
         "safety/value": "yes", "safety/rationale": "", "tools/value": ["search_lore"]},
        {"request": {"scenario_id": "b"}, "tool_selection/value": False, "tool_selection/rationale": "move_to not called",
         "safety/value": "no", "safety/rationale": "unsafe", "tools/value": []},
        {"request": {"scenario_id": "c"}, "tool_selection/value": math.nan, "tool_selection/rationale": None,
         "safety/value": None, "safety/rationale": None, "tools/value": []},
    ])
    text = summarise(df, ["tool_selection", "safety", "in_character"])
    assert "tool_selection" in text and "1/2" in text
    assert "in_character" in text and "n/a" in text
    assert "b · tool_selection: move_to not called" in text and "b · safety: unsafe" in text
    assert "tools" not in text.replace("tool_selection", "")


def test_errored_rows_are_counted_not_hidden_as_na():
    df = pd.DataFrame([
        {"request": {"scenario_id": "a"}, "safety/value": "yes"},
        {"request": {"scenario_id": "b"}, "safety/value": math.nan, "safety/error_message": "timed out"},
    ])
    assert "1/1  (100%), 1 not scored" in summarise(df, ["safety"])


def test_code_scorer_errors_mean_the_harness_broke():
    from evals.run import harness_errors

    df = pd.DataFrame([
        {"request": {"scenario_id": "a"}, "tool_selection/value": math.nan,
         "tool_selection/error_message": "no eval.details on the trace", "safety/error_message": "timed out"},
        {"request": {"scenario_id": "b"}, "tool_selection/value": math.nan, "tool_selection/error_message": None},
    ])
    assert harness_errors(df, ["tool_selection"]) == ["a · tool_selection: no eval.details on the trace"]
