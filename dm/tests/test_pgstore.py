from types import SimpleNamespace

import agent.pgstore as pg


def test_token_is_cached_then_refreshed(monkeypatch):
    issued = []

    def generate_database_credential(endpoint):
        issued.append(endpoint)
        return SimpleNamespace(token=f"tok-{len(issued)}")

    clock = {"now": 1000.0}
    monkeypatch.setenv("LAKEBASE_ENDPOINT", "projects/p/branches/b/endpoints/e")
    monkeypatch.setattr(pg, "workspace_client",
                        lambda: SimpleNamespace(postgres=SimpleNamespace(generate_database_credential=generate_database_credential)))
    monkeypatch.setattr(pg.time, "time", lambda: clock["now"])
    monkeypatch.setattr(pg, "_token_cache", {"token": None, "at": 0.0})

    assert pg.lakebase_token() == "tok-1"
    clock["now"] += pg.TOKEN_TTL_S - 1
    assert pg.lakebase_token() == "tok-1"
    clock["now"] += 2
    assert pg.lakebase_token() == "tok-2"
    assert issued == ["projects/p/branches/b/endpoints/e"] * 2


def test_schema_sql_creates_all_tables():
    sql = pg.SCHEMA_SQL
    for table in ("characters", "inventory", "quest_flags", "adventures", "npc_cards", "npc_disposition", "adventure_stats"):
        assert f"rpg.{table}" in sql
