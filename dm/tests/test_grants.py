from devtools.grants import (
    game_db_resource,
    lakebase_grant_statements,
    merge_app_resources,
    uc_grant_statements,
)

SP = "11111111-2222-3333-4444-555555555555"


def test_uc_grants_cover_catalog_schema_index_and_trace_tables():
    stmts = uc_grant_statements(SP, "cat", "sch")
    assert f"GRANT USE CATALOG ON CATALOG `cat` TO `{SP}`" in stmts
    assert f"GRANT USE SCHEMA ON SCHEMA `cat`.`sch` TO `{SP}`" in stmts
    assert f"GRANT SELECT ON TABLE `cat`.`sch`.`lore_index` TO `{SP}`" in stmts
    assert f"GRANT MODIFY, SELECT ON TABLE `cat`.`sch`.`dm_otel_spans` TO `{SP}`" in stmts
    assert f"GRANT SELECT ON TABLE `cat`.`sch`.`dm_trace_unified` TO `{SP}`" in stmts
    assert not any("MODIFY" in s and "dm_trace_" in s for s in stmts)  # views take SELECT only


def test_lakebase_grants_are_scoped_to_rpg_schema():
    stmts = lakebase_grant_statements(SP)
    assert stmts == [
        f'GRANT USAGE ON SCHEMA rpg TO "{SP}"',
        f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rpg TO "{SP}"',
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA rpg GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{SP}"',
    ]


def test_game_db_resource_shape():
    r = game_db_resource()
    assert r == {"name": "game-db", "postgres": {
        "branch": "projects/databricks-adventure/branches/production",
        "database": "projects/databricks-adventure/branches/production/databases/databricks-postgres",
        "permission": "CAN_CONNECT_AND_CREATE"}}


def test_merge_app_resources_replaces_by_name_and_keeps_others():
    exp = {"name": "agentbricks-trace-experiment", "experiment": {"experiment_id": "1"}}
    old = {"name": "game-db", "postgres": {"branch": "old"}}
    merged = merge_app_resources([exp, old], game_db_resource())
    assert merged[0] == exp and merged[1] == game_db_resource() and len(merged) == 2
    assert merge_app_resources([exp], game_db_resource()) == [exp, game_db_resource()]


from types import SimpleNamespace

from devtools import grants


def _status(state, msg=None):
    return SimpleNamespace(status=SimpleNamespace(state=SimpleNamespace(value=state),
                                                  error=SimpleNamespace(message=msg) if msg else None),
                           statement_id="st-1")


def test_uc_grants_poll_pending_statements_to_completion(monkeypatch):
    monkeypatch.setattr(grants.time, "sleep", lambda s: None)
    polls = iter([_status("RUNNING"), _status("SUCCEEDED")])
    w = SimpleNamespace(statement_execution=SimpleNamespace(
        execute_statement=lambda **kw: _status("PENDING"),
        get_statement=lambda statement_id: next(polls)))
    assert grants.apply_uc_grants(w, "wh", ["GRANT X"]) == []


def test_uc_grants_report_terminal_failures_only(monkeypatch):
    w = SimpleNamespace(statement_execution=SimpleNamespace(
        execute_statement=lambda **kw: _status("FAILED", "PERMISSION_DENIED"), get_statement=None))
    assert grants.apply_uc_grants(w, "wh", ["GRANT Y"]) == ["GRANT Y: PERMISSION_DENIED"]


def test_lakebase_grants_are_independent_autocommit_statements():
    executed = []

    class Conn:
        autocommit = False

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, stmt):
            assert self.autocommit is True
            if "INSERT" in stmt:
                raise RuntimeError("boom")
            executed.append(stmt)

    failures = grants.apply_lakebase_grants(["A", "B INSERT", "C"], connect=Conn)
    assert executed == ["A", "C"] and len(failures) == 1 and "B INSERT" in failures[0]


def test_lakebase_connection_error_is_a_reported_failure():
    def broken():
        raise KeyError("PGHOST")

    failures = grants.apply_lakebase_grants(["A"], connect=broken)
    assert failures and "connect" in failures[0]


def test_cli_errors_include_stderr(monkeypatch):
    import subprocess

    def fail(*a, **k):
        raise subprocess.CalledProcessError(1, a[0], output="", stderr="App not found: nope")

    monkeypatch.setattr(grants.subprocess, "run", fail)
    import pytest

    with pytest.raises(RuntimeError, match="App not found"):
        grants._cli("p", "apps", "get", "nope")


def test_model_service_grant_is_execute_for_the_dm():
    from devtools.grants import grant_model_service, model_service_grant_body

    assert model_service_grant_body(SP) == {"changes": [{"principal": SP, "add": ["EXECUTE"]}]}
    calls = []
    grant_model_service("p", "cat.sch.dm_model", SP, run=lambda cmd: calls.append(cmd))
    [cmd] = calls
    assert cmd[:5] == ["databricks", "grants", "update", "model_service", "cat.sch.dm_model"]
