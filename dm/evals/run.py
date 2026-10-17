"""`make eval`: play every scenario against the real DM and print its report card.

Spec: docs/superpowers/specs/2026-10-17-m6-evals-design.md. Report only: exits 0 whatever the scores.
"""

import json
import math
import os
import sys

import mlflow
from dotenv import load_dotenv

from evals.harness import make_predict_fn
from evals.scenarios import Scenario, load_scenarios
from evals.scorers import CODE_SCORERS, judges

EXPERIMENT = "/Shared/databricks-adventure/dm-evals"
PASS, FAIL = (True, "yes"), (False, "no")


def to_dataset(scenarios: list[Scenario]) -> list[dict]:
    return [{"inputs": {"scenario_id": s.id, "player_input": s.input},
             "expectations": s.expect.model_dump(exclude_defaults=True)} for s in scenarios]


def _scenario_id(request) -> str:
    if isinstance(request, str):
        request = json.loads(request)
    return request.get("scenario_id", "?")


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def summarise(df, names: list[str]) -> str:
    """Pass rate per scorer (n/a when nothing applied), then each failure with its rationale.

    Only the given scorer names are read: `result_df` also has `<key>/value` columns for expectations.
    """
    lines, failures = ["The DM's report card", ""], []
    for name in names:
        column = f"{name}/value"
        values = [] if column not in df else [v for v in df[column] if not _missing(v)]
        passed = sum(1 for v in values if v in PASS)
        failed = sum(1 for v in values if v in FAIL)
        rate = f"{passed}/{passed + failed}  ({round(100 * passed / (passed + failed))}%)" if passed + failed else "n/a"
        lines.append(f"  {name:<26}{rate}")
        if column in df:
            for _, row in df.iterrows():
                if not _missing(row[column]) and row[column] in FAIL:
                    failures.append(f"  - {_scenario_id(row['request'])} · {name}: {row.get(f'{name}/rationale') or ''}")
    return "\n".join([*lines, "", "Failures", *(failures or ["  none"])])


def main() -> int:
    load_dotenv()
    if not os.getenv("LORE_INDEX"):
        print("Set LORE_INDEX (make eval passes it from CATALOG/SCHEMA).", file=sys.stderr)
        return 2
    # The dice are seeded through a module global, so scenarios must play one at a time.
    os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_WORKERS", "1")
    from databricks.sdk import WorkspaceClient
    from databricks_langchain import ChatDatabricks

    from agent.agent import MODEL

    scenarios = load_scenarios()
    mlflow.set_tracking_uri("databricks")
    mlflow.set_experiment(EXPERIMENT)
    mlflow.langchain.autolog()
    llm = ChatDatabricks(endpoint=MODEL, workspace_client=WorkspaceClient(), use_ai_gateway=True)
    scorers = [*CODE_SCORERS, *judges()]
    result = mlflow.genai.evaluate(data=to_dataset(scenarios), predict_fn=make_predict_fn(scenarios, llm),
                                   scorers=scorers)
    print(summarise(result.result_df, [s.name for s in scorers]))
    print(f"\nModel {MODEL}. Full results: MLflow experiment {EXPERIMENT}, run {result.run_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
