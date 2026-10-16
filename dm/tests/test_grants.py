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
