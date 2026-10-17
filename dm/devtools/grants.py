"""Least-privilege access for the deployed DM's service principal, applied after each deploy."""

import json
import subprocess
import sys
import time

TRACE_TABLES = ("otel_annotations", "otel_logs", "otel_metrics", "otel_spans")
TRACE_VIEWS = ("trace_metadata", "trace_unified")


def uc_grant_statements(sp: str, catalog: str, schema: str, trace_prefix: str = "dm") -> list[str]:
    fq = f"`{catalog}`.`{schema}`"
    stmts = [
        f"GRANT USE CATALOG ON CATALOG `{catalog}` TO `{sp}`",
        f"GRANT USE SCHEMA ON SCHEMA {fq} TO `{sp}`",
        f"GRANT SELECT ON TABLE {fq}.`lore_index` TO `{sp}`",
    ]
    stmts += [f"GRANT MODIFY, SELECT ON TABLE {fq}.`{trace_prefix}_{t}` TO `{sp}`" for t in TRACE_TABLES]
    stmts += [f"GRANT SELECT ON TABLE {fq}.`{trace_prefix}_{v}` TO `{sp}`" for v in TRACE_VIEWS]
    return stmts


def lakebase_grant_statements(sp: str) -> list[str]:
    return [
        f'GRANT USAGE ON SCHEMA rpg TO "{sp}"',
        f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rpg TO "{sp}"',
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA rpg GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{sp}"',
    ]


def game_db_resource(project: str = "databricks-adventure") -> dict:
    branch = f"projects/{project}/branches/production"
    return {"name": "game-db", "postgres": {"branch": branch, "database": f"{branch}/databases/databricks-postgres",
                                            "permission": "CAN_CONNECT_AND_CREATE"}}


def merge_app_resources(current: list[dict], wanted: dict) -> list[dict]:
    kept = [r for r in current if r.get("name") != wanted["name"]]
    return [*kept, wanted]


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"{' '.join(cmd[:3])} failed: {(e.stderr or e.stdout or '').strip()}") from e


def _cli(profile: str, *args: str) -> dict:
    return json.loads(_run(["databricks", *args, "--profile", profile, "-o", "json"]).stdout or "{}")


def attach_game_db(profile: str, app: str) -> str:
    """Attach the Lakebase game DB as an app resource (deploy preserves it). Returns the SP client id."""
    current = _cli(profile, "apps", "get", app)
    resources = merge_app_resources(current.get("resources") or [], game_db_resource())
    body = json.dumps({"update_mask": "resources", "app": {"resources": resources}})
    _run(["databricks", "apps", "create-update", app, "--json", body, "--profile", profile])
    return current["service_principal_client_id"]


_TERMINAL = {"SUCCEEDED", "FAILED", "CANCELED", "CLOSED"}


def apply_uc_grants(w, warehouse_id: str, statements: list[str], deadline_s: float = 600) -> list[str]:
    """Run each GRANT to completion. A cold warehouse returns PENDING/RUNNING first: poll, don't fail."""
    failures = []
    for stmt in statements:
        r = w.statement_execution.execute_statement(statement=stmt, warehouse_id=warehouse_id, wait_timeout="30s")
        give_up = time.monotonic() + deadline_s
        while r.status.state.value not in _TERMINAL and time.monotonic() < give_up:
            time.sleep(3)
            r = w.statement_execution.get_statement(r.statement_id)
        if r.status.state.value != "SUCCEEDED":
            failures.append(f"{stmt}: {r.status.error.message if r.status.error else r.status.state.value}")
    return failures


def apply_lakebase_grants(statements: list[str], connect=None) -> list[str]:
    """Each GRANT is its own autocommit statement, so one failure can't undo the others."""
    if connect is None:
        from agent.pgstore import connect_from_env as connect
    try:
        conn = connect()
    except Exception as e:  # noqa: BLE001 - report, don't crash before the UC failures are printed
        return [f"Lakebase connect failed (is the PG* env from lakebase_env.sh loaded?): {e}"]
    failures = []
    with conn:
        conn.autocommit = True
        for stmt in statements:
            try:
                conn.execute(stmt)
            except Exception as e:  # noqa: BLE001 - collect and report every failure
                failures.append(f"{stmt}: {e}")
    return failures


def grant_warehouse(w, warehouse_id: str, sp: str) -> None:
    from databricks.sdk.service.sql import WarehouseAccessControlRequest, WarehousePermissionLevel

    w.warehouses.update_permissions(warehouse_id, access_control_list=[
        WarehouseAccessControlRequest(service_principal_name=sp, permission_level=WarehousePermissionLevel.CAN_USE)])


def model_service_grant_body(sp: str) -> dict:
    return {"changes": [{"principal": sp, "add": ["EXECUTE"]}]}


def grant_model_service(profile: str, full_name: str, sp: str, run=_run) -> None:
    """EXECUTE lets the DM query its guarded model service (the privilege account users hold on system.ai)."""
    run(["databricks", "grants", "update", "model_service", full_name,
         "--json", json.dumps(model_service_grant_body(sp)), "--profile", profile])


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 5:
        print("usage: python -m devtools.grants <profile> <app> <catalog> <schema> <warehouse_id>", file=sys.stderr)
        return 2
    profile, app, catalog, schema, warehouse_id = args
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient(profile=profile)
    try:
        sp = attach_game_db(profile, app)
    except RuntimeError as e:
        print(f"GRANT FAILED: could not attach game-db: {e}", file=sys.stderr)
        return 1
    failures = apply_uc_grants(w, warehouse_id, uc_grant_statements(sp, catalog, schema))
    failures += apply_lakebase_grants(lakebase_grant_statements(sp))
    try:
        grant_warehouse(w, warehouse_id, sp)
    except Exception as e:  # noqa: BLE001
        failures.append(f"warehouse CAN_USE: {e}")
    try:
        grant_model_service(profile, f"{catalog}.{schema}.dm_model", sp)
    except RuntimeError as e:
        failures.append(f"model service EXECUTE: {e}")
    for f in failures:
        print(f"GRANT FAILED: {f}", file=sys.stderr)
    print(f"service principal {sp}: game-db attached; {len(failures)} grant failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
