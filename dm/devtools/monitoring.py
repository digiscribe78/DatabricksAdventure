"""make monitoring: the evals' judges, registered on the live play traces and sampled (MLflow production monitoring, Beta).

make eval scores seeded scenarios offline (dm-evals); this judges a sample of real games in dm-traces.
Only LLM judges: registered code scorers must be defined in a Databricks notebook, and ours read
details only the eval harness records.
"""

import sys

from mlflow.genai.scorers import Guidelines, Safety, ScorerSamplingConfig

from evals.scorers import IN_CHARACTER, PLAYER_AGENCY

TRACES_EXPERIMENT = "/Shared/databricks-adventure/dm-traces"
# Same names and wording as the eval judges, so live and offline scores compare directly.
JUDGES = [
    ("safety", Safety(), 1.0),
    ("in_character", Guidelines(name="in_character", guidelines=IN_CHARACTER), 0.25),
    ("player_agency", Guidelines(name="player_agency", guidelines=PLAYER_AGENCY), 0.25),
]


def ensure_judges(experiment_id: str, registry) -> None:
    """Register each judge, or update its sampling if it's already registered."""
    existing = {s.name for s in registry.list_scorers(experiment_id=experiment_id)}
    for name, judge, rate in JUDGES:
        sampling = ScorerSamplingConfig(sample_rate=rate)
        if name in existing:
            registry.get_scorer(name=name, experiment_id=experiment_id).update(
                name=name, experiment_id=experiment_id, sampling_config=sampling)
        else:
            judge.register(name=name, experiment_id=experiment_id).start(
                name=name, experiment_id=experiment_id, sampling_config=sampling)


def stop_all(experiment_id: str, registry) -> None:
    """Pause every judge (sample rate 0); the registrations stay."""
    for s in registry.list_scorers(experiment_id=experiment_id):
        s.stop(name=s.name, experiment_id=experiment_id)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) not in (1, 2) or (len(args) == 2 and args[1] != "stop"):
        print("usage: python -m devtools.monitoring <warehouse_id> [stop]", file=sys.stderr)
        return 2
    import mlflow
    from mlflow.genai import scorers as registry
    from mlflow.tracing import set_databricks_monitoring_sql_warehouse_id

    mlflow.set_tracking_uri("databricks")
    exp = mlflow.get_experiment_by_name(TRACES_EXPERIMENT)
    if exp is None:
        print(f"{TRACES_EXPERIMENT} not found: run make deploy-agent first", file=sys.stderr)
        return 1
    if len(args) == 2:
        stop_all(exp.experiment_id, registry)
        print("live monitoring paused")
    else:
        set_databricks_monitoring_sql_warehouse_id(sql_warehouse_id=args[0], experiment_id=exp.experiment_id)
        ensure_judges(exp.experiment_id, registry)
    for s in registry.list_scorers(experiment_id=exp.experiment_id):
        print(f"  {s.name}: sample rate {getattr(s, 'sample_rate', None)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
