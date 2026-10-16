"""Create (idempotently) the DM's trace experiment with a Unity Catalog trace location.

Deployed Apps can't upload span artifacts to experiment storage, so traces go to UC tables.
"""

import os
import sys

EXPERIMENT = "/Shared/databricks-adventure/dm-traces"


def ensure_trace_experiment(name: str, catalog: str, schema: str, prefix: str, warehouse_id: str) -> str:
    import mlflow
    from databricks.sdk import WorkspaceClient
    from mlflow.entities.trace_location import UnityCatalog

    WorkspaceClient().workspace.mkdirs(name.rsplit("/", 1)[0])
    mlflow.set_tracking_uri("databricks")
    os.environ["MLFLOW_TRACING_SQL_WAREHOUSE_ID"] = warehouse_id
    existing = mlflow.get_experiment_by_name(name)
    if existing is not None:
        return existing.experiment_id
    exp = mlflow.set_experiment(experiment_name=name, trace_location=UnityCatalog(
        catalog_name=catalog, schema_name=schema, table_prefix=prefix))
    return exp.experiment_id


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3:
        print("usage: python -m devtools.tracing <catalog> <schema> <warehouse_id>", file=sys.stderr)
        return 2
    print(f"trace experiment {EXPERIMENT}: {ensure_trace_experiment(EXPERIMENT, args[0], args[1], 'dm', args[2])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
