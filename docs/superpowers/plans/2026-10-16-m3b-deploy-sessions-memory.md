# Milestone 3b: Deployed DM with Sessions, Memory and Player Identity

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The DM runs on **Agent Runtime** (`agent-bricks-dm`) with everything it needs:
- its Lakebase save games;
- the AI Search lore;
- the managed **session store**, so conversations persist across restarts;
- the managed **memory store**, so the DM recalls past adventures with this player, filled by a Dreamer pipeline;
- **traces in Unity Catalog**;
- and saves owned by the **signed-in player**.

One command, `make deploy-agent PROFILE=… CATALOG=…`, does all of it from a clean build copy, so tracked files never carry workspace-specific values.

**Architecture and findings (from the 2026-10-16 spike deploy, all verified live):**
- **The app's network blocks trace span uploads to experiment artifact storage.** The presigned `*.storage.cloud.databricks.com` URL is refused. **The fix: a Unity Catalog trace location.** Create the experiment with `trace_location=UnityCatalog(catalog, schema, table_prefix="dm")`, bind it with `agentbricks tracing bind`, set `MLFLOW_TRACING_SQL_WAREHOUSE_ID`, and grant the app service principal `USE CATALOG`, `USE SCHEMA`, `MODIFY`+`SELECT` on the four `dm_otel_*` tables, `SELECT` on the two `dm_trace_*` views, and `CAN_USE` on the warehouse. Verified: 17 spans landed in `dm_otel_spans`.
- **`agentbricks deploy` rewrites `app.yaml`** (experiment ID, store names, service principal ID, runtime DB) **and `agent.toml`** (`deployment_name`). So we deploy from a copy at `$TMPDIR/databricks-adventure-dm`. It has to be outside the repo, because the source sync honours `.gitignore`, so `build/` uploads nothing. And it must leave out `.databricks`, because stale sync state uploads only part of the source and the app then crashes with `No module named 'runtime'`.
- **The runtime store is managed** (`_USE_MANAGED_RUNTIME_STORE = True`), so the only app resource is the trace experiment. Nothing injects `PG*`. We attach our own `postgres` resource (`game-db`). `deploy` keeps resources it doesn't own (`AppsClient.reconcile_resources`).
- **Identity:** `[auth.user] required = true` makes the runtime read `X-Forwarded-User` from the Apps ingress, namespace `session_id` per user, and expose `request_auth.namespace(kind, value)`, a stable per-principal hash. That hash becomes the **player ID**. Locally, the principal is `local-developer`.
- **Memory API:** `POST /api/2.0/agents/memory-stores/{store}/entries:search` with `{actor_id, query, limit}` returns `managed_memory_entries[].content`. `memory_tools(actor)` already gives the model `remember` and `recall` when `AGENT_MEMORY_STORE` is set. The Dreamer pipeline (`agentbricks memory pipeline create --memory-store … --session-store … --instructions @file`) distils sessions into memories.

**Tech Stack:** Agent Bricks CLI 0.5.1 (`deploy`, `tracing bind`, `memory pipeline`), MLflow 3.17 UC trace locations, the Databricks SDK (`statement_execution`, `warehouses`, `apps`), psycopg 3, and the M3a stack.

**Spec:** `docs/superpowers/specs/2026-10-16-databricks-rpg-design.md`, §2, §7, §9 and §15 (M3b). Builds on the merged M3a and the history window.

## Global Constraints

- The dev profile is `brickbots`, the catalog is `serverless_stable_brickbots_catalog`, and the schema is `databricks_adventure`, all passed as arguments. Tracked code and config never hold a host, workspace ID, service principal ID, experiment ID, warehouse ID or email.
- The deployment name is `dm`, giving the app `agent-bricks-dm`. The trace experiment is `/Shared/databricks-adventure/dm-traces`, with UC trace tables `${catalog}.${schema}.dm_*`.
- The Lakebase app resource is named `game-db`: branch `projects/databricks-adventure/branches/production`, database `projects/databricks-adventure/branches/production/databases/databricks-postgres`, permission `CAN_CONNECT_AND_CREATE`.
- The service principal gets **only** what it needs:
  - `USAGE` on schema `rpg`, and `SELECT, INSERT, UPDATE, DELETE` on its tables, plus default privileges for future tables;
  - `SELECT` on `lore_index`;
  - the trace grants listed above;
  - warehouse `CAN_USE`.
- **Player identity comes only from the authenticated request** (`request_auth.namespace("player", "self")`) whenever request auth exists. The payload `actor` is honoured only when there's no request auth: local tests and the in-memory dev store.
- Memory recall happens once per session, on the first turn, at most 5 entries. Recalled memories show as a `memory` turn event and are injected into the DM system prompt.
- Commit messages end with `Co-authored-by: Isaac <no-reply@databricks.com>`.

**Spec deltas (recorded in Task 7):**
1. §2/§13: traces are stored in Unity Catalog (`dm_*` tables), plus a warehouse.
2. §13: the agent deploys from a build copy via `make deploy-agent`.
3. §7: the player ID is the runtime's per-principal namespace hash, not an email.
4. §7: memory is recalled at session start (a 🧠 event), plus the model's `remember` and `recall` tools and a Dreamer pipeline.

## Review Focus

1. **A deployed request where the client sends someone else's `actor`, or reuses another player's `session_id`.** The payload actor is ignored, and the runtime's session namespacing plus `GameStore.owner` keep the saves apart. Pinned in Task 3.
2. **The memory store is unset or unreachable, or returns nothing.** The turn still completes, with no memory event and no crash. Pinned in Task 4.
3. **`make deploy-agent` is run twice, or after a failed deploy.** The build copy is rebuilt from scratch (no `.databricks`), the `game-db` resource isn't duplicated, and the grants are idempotent. Pinned in Tasks 1, 2 and 6.
4. **Tracked files after a deploy.** `git status` is clean: no rewritten `app.yaml` or `agent.toml`. Pinned in Task 6.
5. **The service principal is missing one grant** (index, `rpg` schema, warehouse). The deploy script reports which grant failed instead of silently continuing. Pinned in Task 2.

---

## File structure (end of M3b)

```
dm/devtools/__init__.py
dm/devtools/build.py         copy_source(), render_app_yaml()       (pure + filesystem; tested)
dm/devtools/grants.py        uc_grant_statements(), lakebase_grant_statements(), merge_app_resources(),
                             apply_* functions (SDK/psycopg/CLI) and the CLI `python -m devtools.grants`
dm/devtools/tracing.py       ensure_trace_experiment() and the CLI `python -m devtools.tracing`
dm/agent.toml                (modified) tracing → /Shared/databricks-adventure/dm-traces; [auth.user] required = true
dm/agent/memory.py           recall_memories(actor, limit) via the memory-store REST API
dm/agent/dm_graph.py         (modified) recall at session start, `memories` state, memory events
dm/agent/prompts.py          (modified) "What you remember about this player"
dm/agent/agent.py            (modified) passes recall to the graph
dm/runtime/adapter.py        (modified) player identity from request_auth
content/dreamer-instructions.md   what the Dreamer should remember
scripts/deploy_agent.sh      build copy → env → agentbricks deploy → grants
Makefile                     (modified) deploy-agent, memory-pipeline, destroy also removes the agent
dm/scripts/smoke_turns.sh    (modified) BASE + bearer TOKEN for deployed runs
dm/tests/test_build.py, test_grants.py, test_memory.py, (modified) test_agent.py, test_dm_graph.py
```

---

### Task 1: Build copy and `app.yaml` rendering

**Files:**
- Create: `dm/devtools/__init__.py`, `dm/devtools/build.py`
- Test: `dm/tests/test_build.py`

**Interfaces:**
- Produces:
  - `devtools.build.EXCLUDES`, a tuple of patterns: `.venv`, `.env`, `.databricks`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `mlflow.db*`, `app.agentbricksdev.yaml`
  - `devtools.build.copy_source(src: Path, dst: Path) -> None`, which deletes `dst` first, then copies `src` without the `EXCLUDES`
  - `devtools.build.render_app_yaml(text: str, env: dict[str, str]) -> str`. It parses YAML, upserts each `env` entry as `{name, value}` (replacing any existing value or `valueFrom` with the same name), keeps everything else, and returns YAML.
  - CLI: `python -m devtools.build <src> <dst> KEY=VALUE ...`, which copies and then rewrites `dst/app.yaml` with the given env

- [ ] **Step 1: Write the failing tests**

`dm/tests/test_build.py`:
```python
import subprocess
import sys
from pathlib import Path

import yaml
from devtools.build import EXCLUDES, copy_source, render_app_yaml


def test_render_app_yaml_adds_and_replaces_env():
    base = "command: [uv, run, start-server]\nenv:\n  - name: KEEP\n    value: a\n  - name: SWAP\n    valueFrom: x\n"
    out = yaml.safe_load(render_app_yaml(base, {"SWAP": "b", "NEW": "c"}))
    assert out["command"] == ["uv", "run", "start-server"]
    assert out["env"] == [{"name": "KEEP", "value": "a"}, {"name": "SWAP", "value": "b"}, {"name": "NEW", "value": "c"}]


def test_render_app_yaml_without_env_section():
    out = yaml.safe_load(render_app_yaml('command: ["uv", "run", "start-server"]\n', {"A": "1"}))
    assert out["env"] == [{"name": "A", "value": "1"}]


def test_copy_source_excludes_local_state(tmp_path):
    src = tmp_path / "src"
    for rel in ["app.yaml", "agent/agent.py", ".env", ".venv/x", ".databricks/sync.json",
                "agent/__pycache__/a.pyc", ".agentbricks/project.toml", ".agentbricks/mlflow.db"]:
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text("x")
    dst = tmp_path / "dst"
    (dst / "stale").mkdir(parents=True)
    copy_source(src, dst)
    copied = sorted(str(p.relative_to(dst)) for p in dst.rglob("*") if p.is_file())
    assert copied == [".agentbricks/project.toml", "agent/agent.py", "app.yaml"]
    assert ".databricks" in EXCLUDES


def test_cli_copies_and_renders(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.yaml").write_text("command: [x]\n")
    dst = tmp_path / "dst"
    subprocess.run([sys.executable, "-m", "devtools.build", str(src), str(dst), "LORE_INDEX=c.s.i"],
                   cwd=Path(__file__).resolve().parents[1], check=True)
    assert yaml.safe_load((dst / "app.yaml").read_text())["env"] == [{"name": "LORE_INDEX", "value": "c.s.i"}]
```

- [ ] **Step 2: Run them and check they fail**

Run: `cd dm && uv run pytest tests/test_build.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'devtools'`.

- [ ] **Step 3: Implement**

`dm/devtools/__init__.py`:
```python
"""Developer tooling for deploying the DM (not imported by the agent at runtime)."""
```

`dm/devtools/build.py`:
```python
"""Build a clean deploy copy of the DM project.

agentbricks deploy rewrites app.yaml and agent.toml with workspace-specific values, and its source
sync honours .gitignore and incremental .databricks state. So we deploy from a fresh copy outside
the repo, with our env rendered into app.yaml.
"""

import shutil
import sys
from pathlib import Path

import yaml

EXCLUDES = (".venv", ".env", ".databricks", "__pycache__", ".pytest_cache", ".ruff_cache",
            "mlflow.db*", "app.agentbricksdev.yaml")


def copy_source(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*EXCLUDES))


def render_app_yaml(text: str, env: dict[str, str]) -> str:
    doc = yaml.safe_load(text) or {}
    entries = [e for e in doc.get("env") or [] if isinstance(e, dict)]
    by_name = {e.get("name"): e for e in entries}
    for name, value in env.items():
        if name in by_name:
            by_name[name].pop("valueFrom", None)
            by_name[name]["value"] = value
        else:
            entries.append({"name": name, "value": value})
    doc["env"] = entries
    return yaml.safe_dump(doc, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 2:
        print("usage: python -m devtools.build <src> <dst> [KEY=VALUE ...]", file=sys.stderr)
        return 2
    src, dst = Path(args[0]), Path(args[1])
    env = dict(a.split("=", 1) for a in args[2:])
    copy_source(src, dst)
    app_yaml = dst / "app.yaml"
    app_yaml.write_text(render_app_yaml(app_yaml.read_text(), env))
    print(f"built {dst} with env {sorted(env)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run them and check they pass**

Run: `cd dm && uv run pytest tests/test_build.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add dm/devtools dm/tests/test_build.py
git commit -m "feat(devtools): clean build copy and app.yaml env rendering for agent deploys

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 2: Grants and app resources for the agent's service principal

**Files:**
- Create: `dm/devtools/grants.py`, `dm/devtools/tracing.py`
- Test: `dm/tests/test_grants.py`

**Interfaces:**
- Produces (pure, tested):
  - `TRACE_TABLES = ("otel_annotations", "otel_logs", "otel_metrics", "otel_spans")` and `TRACE_VIEWS = ("trace_metadata", "trace_unified")`
  - `uc_grant_statements(sp: str, catalog: str, schema: str, trace_prefix: str = "dm") -> list[str]`, which includes `SELECT` on `lore_index`
  - `lakebase_grant_statements(sp: str) -> list[str]`
  - `game_db_resource(project: str = "databricks-adventure") -> dict`
  - `merge_app_resources(current: list[dict], wanted: dict) -> list[dict]`, which replaces any entry with the same `name` and keeps the rest
- Produces (side-effecting, used by the CLI):
  - `apply_uc_grants(w, warehouse_id, statements) -> list[str]`, which returns the failures
  - `apply_lakebase_grants(statements)`, as the owner, using `agent.pgstore.connect_from_env`
  - `grant_warehouse(w, warehouse_id, sp)`
  - `attach_game_db(profile, app)`
- CLI: `python -m devtools.grants <profile> <app> <catalog> <schema> <warehouse_id>`. It exits non-zero and lists every failed grant.
- `devtools.tracing.ensure_trace_experiment(name, catalog, schema, prefix, warehouse_id) -> str` (the experiment ID). It's idempotent, and creates the `/Shared/...` parent folder. CLI: `python -m devtools.tracing <catalog> <schema> <warehouse_id>`.

- [ ] **Step 1: Write the failing tests**

`dm/tests/test_grants.py`:
```python
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
```

- [ ] **Step 2: Run them and check they fail**

Run: `cd dm && uv run pytest tests/test_grants.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'devtools.grants'`.

- [ ] **Step 3: Implement the grants**

`dm/devtools/grants.py`:
```python
"""Least-privilege access for the deployed DM's service principal, applied after each deploy."""

import json
import subprocess
import sys

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


def _cli(profile: str, *args: str) -> dict:
    out = subprocess.run(["databricks", *args, "--profile", profile, "-o", "json"],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout or "{}")


def attach_game_db(profile: str, app: str) -> str:
    """Attach the Lakebase game DB as an app resource (deploy preserves it). Returns the SP client id."""
    current = _cli(profile, "apps", "get", app)
    resources = merge_app_resources(current.get("resources") or [], game_db_resource())
    body = json.dumps({"update_mask": "resources", "app": {"resources": resources}})
    subprocess.run(["databricks", "apps", "create-update", app, "--json", body, "--profile", profile],
                   capture_output=True, text=True, check=True)
    return current["service_principal_client_id"]


def apply_uc_grants(w, warehouse_id: str, statements: list[str]) -> list[str]:
    failures = []
    for stmt in statements:
        r = w.statement_execution.execute_statement(statement=stmt, warehouse_id=warehouse_id, wait_timeout="50s")
        if r.status.state.value != "SUCCEEDED":
            failures.append(f"{stmt}: {r.status.error.message if r.status.error else r.status.state}")
    return failures


def apply_lakebase_grants(statements: list[str]) -> list[str]:
    from agent.pgstore import connect_from_env

    failures = []
    with connect_from_env() as conn:
        for stmt in statements:
            try:
                conn.execute(stmt)
            except Exception as e:  # noqa: BLE001 - collect and report every failure
                failures.append(f"{stmt}: {e}")
                conn.rollback()
    return failures


def grant_warehouse(w, warehouse_id: str, sp: str) -> None:
    from databricks.sdk.service.sql import WarehouseAccessControlRequest, WarehousePermissionLevel

    w.warehouses.update_permissions(warehouse_id, access_control_list=[
        WarehouseAccessControlRequest(service_principal_name=sp, permission_level=WarehousePermissionLevel.CAN_USE)])


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 5:
        print("usage: python -m devtools.grants <profile> <app> <catalog> <schema> <warehouse_id>", file=sys.stderr)
        return 2
    profile, app, catalog, schema, warehouse_id = args
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient(profile=profile)
    sp = attach_game_db(profile, app)
    failures = apply_uc_grants(w, warehouse_id, uc_grant_statements(sp, catalog, schema))
    failures += apply_lakebase_grants(lakebase_grant_statements(sp))
    try:
        grant_warehouse(w, warehouse_id, sp)
    except Exception as e:  # noqa: BLE001
        failures.append(f"warehouse CAN_USE: {e}")
    for f in failures:
        print(f"GRANT FAILED: {f}", file=sys.stderr)
    print(f"service principal {sp}: game-db attached; {len(failures)} grant failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Implement the trace experiment helper**

`dm/devtools/tracing.py`:
```python
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
```

- [ ] **Step 5: Run the tests and check they pass**

Run: `cd dm && uv run pytest tests/test_grants.py -q && uvx ruff check devtools --select F`
Expected: 4 passed, and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit**

```bash
git add dm/devtools/grants.py dm/devtools/tracing.py dm/tests/test_grants.py
git commit -m "feat(devtools): least-privilege grants, game-db app resource and UC trace experiment helpers

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 3: Player identity from the authenticated request

**Files:**
- Modify: `dm/agent.toml`, `dm/runtime/adapter.py`
- Test: `dm/tests/test_agent.py`

**Interfaces:**
- Consumes: `context.request_auth` (`RequestAuthContext`, with `.namespace(kind, value) -> str`)
- Produces: `runtime.adapter._player(payload, session_id, auth) -> str`. With `auth`, it returns `auth.namespace("player", "self")` and ignores `payload["actor"]`. Without `auth`, it returns `payload["actor"]` or `session_id`, as before. `_invoke_agent` uses it for both the graph actor and `_ensure_adventure`.
- `agent.toml` adds the following, which makes the runtime require request-user auth when deployed:
```toml
[auth.user]
required = true
```

- [ ] **Step 1: Write the failing tests**

Append to `dm/tests/test_agent.py`:
```python
class FakeAuth:
    def __init__(self, principal):
        self.principal = principal

    def namespace(self, kind, value):
        return f"{self.principal}:{kind}:{value}"

    def client_for(self, mode):
        raise AssertionError("not used")


def authed_ctx(principal, session="s-auth"):
    return SimpleNamespace(invocation_id="inv-1", session_id=session, emit=AsyncMock(), request_auth=FakeAuth(principal))


@pytest.mark.asyncio
async def test_authenticated_player_owns_new_adventure_and_payload_actor_is_ignored(mem_store, capture_run):
    from runtime.adapter import invoke

    await invoke({"messages": [], "new_game": {"name": "Elowen", "archetype": "mage"}, "actor": "spoofed"},
                 authed_ctx("alice"))
    assert mem_store.owner("s-auth") == "alice:player:self"
    assert capture_run[0]["actor"] == "alice:player:self"


@pytest.mark.asyncio
async def test_authenticated_player_cannot_use_another_players_adventure(mem_store, capture_run):
    from runtime.adapter import invoke

    mem_store.create_adventure("s-auth", "alice:player:self", "Elowen", "mage")
    with pytest.raises(PermissionError):
        await invoke({"messages": [{"role": "user", "content": "hi"}], "actor": "alice:player:self"},
                     authed_ctx("mallory"))


def test_agent_toml_requires_user_auth():
    import tomllib
    from pathlib import Path

    doc = tomllib.loads((Path(__file__).resolve().parents[1] / "agent.toml").read_text())
    assert doc["auth"]["user"]["required"] is True
    assert doc["tracing"]["experiment_name"] == "/Shared/databricks-adventure/dm-traces"
```

- [ ] **Step 2: Run them and check they fail**

Run: `cd dm && uv run pytest tests/test_agent.py -q -k "authenticated or requires_user"`
Expected: 3 FAIL. The owner is `spoofed`-derived or the payload actor, and `KeyError: 'auth'`.

- [ ] **Step 3: Implement**

In `dm/agent.toml`, append:
```toml

[auth.user]
required = true
```
(The `[tracing]` `experiment_name` was already rebound to `/Shared/databricks-adventure/dm-traces` during the spike; keep that change.)

In `dm/runtime/adapter.py`, add below `_actor`:
```python
def _player(payload: dict[str, Any], session_id: str, auth: Any) -> str:
    """Who is playing: the authenticated principal when deployed, never a client-supplied value."""
    if auth is not None:
        return auth.namespace("player", "self")
    return _actor(payload, session_id)
```
In `_invoke_agent`, replace these lines:
```python
    actor = _actor(payload, session_id)
    auth = getattr(context, "request_auth", None)
    if auth and payload.get("actor"):
        actor = auth.namespace("actor", actor)
```
with:
```python
    auth = getattr(context, "request_auth", None)
    actor = _player(payload, session_id, auth)
```
In `recover`, `actor = _actor(payload, session_id)` stays as it is. Recovery of request-user invocations is refused by the runtime before agent code runs.

- [ ] **Step 4: Run the tests**

Run: `cd dm && uv run pytest -q`
Expected: everything passes, including 3 new tests.

- [ ] **Step 5: Commit**

```bash
git add dm/agent.toml dm/runtime/adapter.py dm/tests/test_agent.py
git commit -m "feat(dm): player identity from the authenticated request; UC trace experiment binding

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 4: Recall memories at session start

**Files:**
- Create: `dm/agent/memory.py`
- Modify: `dm/agent/dm_graph.py`, `dm/agent/prompts.py`, `dm/agent/agent.py`
- Test: `dm/tests/test_memory.py`, plus `dm/tests/test_dm_graph.py` (append)

**Interfaces:**
- Produces:
  - `agent.memory.recall_memories(actor: str, query: str = RECALL_QUERY, limit: int = 5) -> list[str]`. It returns `[]` when no memory store is configured, and raises on API errors.
  - `RECALL_QUERY = "the player's past adventures, choices, promises and relationships"`
  - `build_dm_graph(..., store, recall: Callable[[str], list[str]] | None = None)`
  - New `DMState` key `memories: list[str]`, set on the session's first turn only, when `memories` isn't in state yet
  - The `compose` events gain `TurnEvent(type="memory", summary="Memory: recalled N things about you", detail={"memories": [...]})` on the turn they were recalled
  - `turn_events` maps the tool names `remember` and `recall` to `memory` events
  - `render_dm_system` adds a `What you remember about this player:` section (or `- nothing yet`)

- [ ] **Step 1: Write the failing tests**

`dm/tests/test_memory.py`:
```python
from types import SimpleNamespace

import agent.memory as memory


def test_no_store_configured_returns_nothing(monkeypatch):
    monkeypatch.setattr(memory, "resolve_memory_store", lambda store=None: None)
    assert memory.recall_memories("p1") == []


def test_recall_searches_actor_partition(monkeypatch):
    calls = []

    class Api:
        def do(self, method, path, body):
            calls.append((method, path, body))
            return {"managed_memory_entries": [{"content": "Spared the thief"}, {"content": "Owes Marta a story"}]}

    monkeypatch.setattr(memory, "resolve_memory_store", lambda store=None: "mem-1")
    monkeypatch.setattr(memory, "_api", lambda: Api())
    assert memory.recall_memories("p1", limit=2) == ["Spared the thief", "Owes Marta a story"]
    method, path, body = calls[0]
    assert method == "POST" and path.endswith("/memory-stores/mem-1/entries:search")
    assert body == {"actor_id": "p1", "query": memory.RECALL_QUERY, "limit": 2}
```
Append to `dm/tests/test_dm_graph.py`:
```python
def test_first_turn_recalls_memories_once_and_emits_event():
    asked = []

    def recall(actor):
        asked.append(actor)
        return ["Spared the thief in the swamp"]

    model = ScriptedModel(replies=[AIMessage(content="ok"), AIMessage(content="ok")], structured=[PROSE, PROSE])
    graph = build_dm_graph(model, [roll_check], checkpointer=InMemorySaver(), store=new_store(), recall=recall)
    cfg = {"configurable": {"thread_id": "t1", "actor_id": "player-1"}}
    first = graph.invoke({"messages": []}, cfg)["turn"]
    second = graph.invoke({"messages": [{"role": "user", "content": "hi"}]}, cfg)["turn"]
    assert asked == ["player-1"]
    assert first["events"][0]["type"] == "memory" and "1 thing" in first["events"][0]["summary"]
    assert [e["type"] for e in second["events"]] == []
    assert "Spared the thief in the swamp" in model.reason_calls[-1][0].content


def test_memory_outage_does_not_break_the_turn():
    def recall(actor):
        raise ConnectionError("memory store down")

    model = ScriptedModel(replies=[AIMessage(content="ok")], structured=[PROSE])
    graph = build_dm_graph(model, [roll_check], checkpointer=InMemorySaver(), store=new_store(), recall=recall)
    turn = graph.invoke({"messages": []}, {"configurable": {"thread_id": "t1", "actor_id": "player-1"}})["turn"]
    assert turn["narration"] == PROSE.narration and turn["events"] == []
```

- [ ] **Step 2: Run them and check they fail**

Run: `cd dm && uv run pytest tests/test_memory.py tests/test_dm_graph.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.memory'`, and `TypeError: ... unexpected keyword argument 'recall'`.

- [ ] **Step 3: Implement `agent.memory`**

`dm/agent/memory.py`:
```python
"""Recall what the DM remembers about a player, from the managed memory store (Lakebase-backed)."""

from databricks_agentkit.langgraph.memory import _AGENTS_API, _api
from databricks_agentkit.runtime.tool_manifest import resolve_memory_store

RECALL_QUERY = "the player's past adventures, choices, promises and relationships"


def recall_memories(actor: str, query: str = RECALL_QUERY, limit: int = 5) -> list[str]:
    store = resolve_memory_store(None)
    if not store:
        return []
    data = _api().do("POST", f"{_AGENTS_API}/memory-stores/{store}/entries:search",
                     body={"actor_id": actor, "query": query, "limit": limit})
    return [e.get("content", "") for e in data.get("managed_memory_entries") or [] if e.get("content")]
```
If `_AGENTS_API` or `_api` aren't importable under those names, open `databricks_agentkit/langgraph/memory.py`, use the names it defines, and record a ruling.

- [ ] **Step 4: Wire recall into the graph and prompt**

In `dm/agent/dm_graph.py`:
1. Add `memories: list[str]` and `memories_new: bool` to `DMState`.
2. Change the `build_dm_graph` signature to `def build_dm_graph(llm, tools, checkpointer=None, *, store: GameStore, recall: Callable[[str], list[str]] | None = None):`, adding `from collections.abc import Callable`.
3. In `load_state`, before `return update`, add:
```python
        if recall is not None and "memories" not in state:
            try:
                memories = recall(config["configurable"].get("actor_id") or _sid(config))
            except Exception:  # noqa: BLE001 - memory is a bonus; never break the turn
                logger.warning("memory recall failed", exc_info=True)
                memories = []
            update["memories"] = memories
            update["memories_new"] = bool(memories)
        else:
            update["memories_new"] = False
```
4. In `_game`, keep the signature. In `dm_reason`, change the system line to `system = SystemMessage(render_dm_system(_game(state), state.get("memories") or []))`.
5. In `compose`'s normal path, insert this before `if state.get("state_summaries"):`:
```python
            if state.get("memories_new"):
                n = len(state["memories"])
                events.insert(0, TurnEvent(type="memory", summary=f"Memory: recalled {n} thing{'s' if n != 1 else ''} about you",
                                           detail={"memories": state["memories"]}))
```
6. Add `_memory_event`, and register both memory tools:
```python
def _memory_event(r: dict) -> TurnEvent:
    return TurnEvent(type="memory", summary="Memory: " + str(r.get("result", r))[:120], detail=r)
```
and extend `_EVENT_BUILDERS` with `"remember": _memory_event, "recall": _memory_event`. The memory tools return plain strings, so in `turn_events` wrap non-dict results: change `r = _tool_result(m) if build else None` to:
```python
        r = (_tool_result(m) or {"result": m.content}) if build else None
```

In `dm/agent/prompts.py`:
1. Append to `DM_SYSTEM`, after the `People here:\n{npcs}` lines: `\nWhat you remember about this player from earlier adventures (weave in naturally, never list):\n{memories}\n`. Also add this rule: `- Use remember to note a lasting fact about the player (a promise, a betrayal, a friendship) when it happens.`
2. Change `render_dm_system(game: GameState)` to `render_dm_system(game: GameState, memories: list[str] = ())`, and pass `memories="\n".join(f"- {m}" for m in memories) or "- nothing yet"` to `format`.

In `dm/agent/agent.py`, in `create_agent_graph`, change the return to:
```python
    from agent.memory import recall_memories

    return build_dm_graph(llm, tools, checkpointer=checkpointer(), store=game_store(), recall=recall_memories)
```

- [ ] **Step 5: Run the tests**

Run: `cd dm && uv run pytest -q && uvx ruff check agent --select F`
Expected: everything passes, including 4 new tests, and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit**

```bash
git add dm/agent/memory.py dm/agent/dm_graph.py dm/agent/prompts.py dm/agent/agent.py dm/tests/test_memory.py dm/tests/test_dm_graph.py
git commit -m "feat(dm): recall player memories at session start with memory events

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 5: Deploy script, Make targets and the Dreamer pipeline

**Files:**
- Create: `scripts/deploy_agent.sh`, `content/dreamer-instructions.md`
- Modify: `Makefile`, `dm/scripts/smoke_turns.sh`

**Interfaces:**
- Consumes: `devtools.build`, `devtools.tracing`, `devtools.grants`, and `scripts/lakebase_env.sh`
- Produces:
  - `scripts/deploy_agent.sh <profile> <catalog> [schema]`, which: gets the default warehouse; ensures the trace experiment; builds a copy at `${TMPDIR:-/tmp}/databricks-adventure-dm` with env `MLFLOW_TRACING_SQL_WAREHOUSE_ID`, `LORE_INDEX` and `LAKEBASE_ENDPOINT`; runs `agentbricks deploy dm --allow-user-scope-update`; then applies the grants (with the Lakebase owner env loaded).
  - `make deploy-agent PROFILE= CATALOG=`
  - `make memory-pipeline PROFILE=`, which creates a manual Dreamer pipeline if missing
  - `make deploy`, which now ends with `deploy-agent`
  - `make destroy`, which also deletes the agent deployment
  - `smoke_turns.sh [BASE]`, with `TOKEN` env adding `Authorization: Bearer $TOKEN`

- [ ] **Step 1: Write the Dreamer instructions**

`content/dreamer-instructions.md`:
```markdown
You are distilling a fantasy role-playing session in the Kingdom of Sparkia into long-term memories
about the PLAYER, so the Dungeon Master can recognise them in a later, separate adventure.

Remember:
- Notable choices and their consequences (spared, betrayed, rescued, stole, refused).
- Relationships with named characters (Marta Quill, the Sweeper, others): favours owed, insults, trust.
- Promises the player made or broke, and unfinished quests.
- The player's style (reckless, cautious, charming, curious) and their character names and archetypes.

Do not remember: dice numbers, HP or gold amounts, item lists, or anything the save game already stores.
Write each memory as one short sentence in British English, e.g. "Spared the river wraith at the Delta Crossing."
```

- [ ] **Step 2: Write the deploy script**

`scripts/deploy_agent.sh`:
```bash
#!/usr/bin/env bash
# Deploy the DM to Agent Runtime from a clean build copy, then grant its service principal access.
# Usage: scripts/deploy_agent.sh <profile> <catalog> [schema]
set -euo pipefail
PROFILE="$1"; CATALOG="$2"; SCHEMA="${3:-databricks_adventure}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${TMPDIR:-/tmp}/databricks-adventure-dm"
APP="agent-bricks-dm"
EP="projects/databricks-adventure/branches/production/endpoints/primary"

WAREHOUSE=$(databricks experimental aitools tools get-default-warehouse --profile "$PROFILE" | tail -1 | tr -d '[:space:]')
echo "warehouse: $WAREHOUSE"
cd "$ROOT/dm"
DATABRICKS_CONFIG_PROFILE="$PROFILE" uv run python -m devtools.tracing "$CATALOG" "$SCHEMA" "$WAREHOUSE"
uv run python -m devtools.build "$ROOT/dm" "$OUT" \
  "MLFLOW_TRACING_SQL_WAREHOUSE_ID=$WAREHOUSE" "LORE_INDEX=$CATALOG.$SCHEMA.lore_index" "LAKEBASE_ENDPOINT=$EP"
(cd "$OUT" && agentbricks --profile "$PROFILE" deploy dm --allow-user-scope-update)
eval "$("$ROOT/scripts/lakebase_env.sh" "$PROFILE")"
DATABRICKS_CONFIG_PROFILE="$PROFILE" uv run python -m devtools.grants "$PROFILE" "$APP" "$CATALOG" "$SCHEMA" "$WAREHOUSE"
# The game-db resource is applied to the running app on the next deployment; roll it out now.
(cd "$OUT" && agentbricks --profile "$PROFILE" deploy dm)
echo "Deployed $APP. Check: git status (tracked files must be unchanged)."
```
Then `chmod +x scripts/deploy_agent.sh`.

- [ ] **Step 3: Update the Makefile**

1. Add `deploy-agent memory-pipeline` to `.PHONY`.
2. In `deploy`, add this as the last line: `$(MAKE) deploy-agent PROFILE=$(PROFILE) CATALOG=$(CATALOG) SCHEMA=$(SCHEMA)`.
3. Add these targets:
```makefile
deploy-agent: check-vars
	scripts/deploy_agent.sh $(PROFILE) $(CATALOG) $(SCHEMA)

memory-pipeline:
	@test -n "$(PROFILE)" || (echo "Set PROFILE=<databricks-profile>" && exit 1)
	cd dm && STORE=$$(grep -A1 '^\[memory_store\]' agent.toml | sed -n 's/name = "\(.*\)"/\1/p') && \
	SESS=$$(grep -A1 '^\[session_store\]' agent.toml | sed -n 's/name = "\(.*\)"/\1/p') && \
	(agentbricks --profile $(PROFILE) memory pipeline list | grep -q dm-dreamer || \
	 agentbricks --profile $(PROFILE) memory pipeline create --memory-store $$STORE --session-store $$SESS \
	   --display-name dm-dreamer --instructions @../content/dreamer-instructions.md --trigger manual)
```
4. In `destroy`, add this as the first line: `-agentbricks --profile $(PROFILE) deployments delete agent-bricks-dm --yes`. If `--yes` isn't a valid flag, check `agentbricks deployments delete --help`, use its non-interactive form, and record a ruling.

- [ ] **Step 4: Teach the smoke script to call the deployed agent**

In `dm/scripts/smoke_turns.sh`:
1. After `SESSION=$(uuidgen)`, add `AUTH=(); [ -n "${TOKEN:-}" ] && AUTH=(-H "Authorization: Bearer $TOKEN")`.
2. In `turn()`, change the curl line to `out=$(curl -sS --fail "$BASE/api/invocations" "${AUTH[@]}" -H 'Content-Type: application/json' -d "$body")`.
3. Add `"  🧠 "` to the event glyph map, i.e. `{"roll":"🎲","lore":"📚","attack":"⚔️ ","state":"💾","memory":"🧠"}`.

- [ ] **Step 5: Check syntax and commit**

Run: `bash -n scripts/deploy_agent.sh` and `bash -n dm/scripts/smoke_turns.sh`.
Expected: no output from either.

Then commit (in its own command, not mixed with `-n` flags):
```bash
git add scripts/deploy_agent.sh content/dreamer-instructions.md Makefile dm/scripts/smoke_turns.sh
git commit -m "feat(deploy): make deploy-agent, Dreamer memory pipeline and authenticated smoke runs

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

### Task 6: Live deploy and authenticated playthrough

**Files:** none new; evidence goes in the ledger. Possibly `scripts/deploy_agent.sh` fixes, each with a ruling.

- [ ] **Step 1: Deploy**

Run: `make deploy-agent PROFILE=brickbots CATALOG=serverless_stable_brickbots_catalog`
Expected:
- The trace experiment ID prints, and the build copy is created.
- Two deploys succeed (`✔ Deployed agent 'agent-bricks-dm'`).
- The grants script reports `0 grant failure(s)` and exits 0.
- **`git status --short` shows nothing.**

If a grant fails, read its message. For the lore index, if `SELECT` alone isn't enough to query, add `CAN_USE` on the AI Search endpoint via `databricks permissions update vector-search-endpoints <endpoint-id>`, and record a ruling.

- [ ] **Step 2: Check the app's resources and env**

```bash
databricks apps get agent-bricks-dm --profile brickbots -o json | jq '[.resources[].name]'
```
Expected: it includes `agentbricks-trace-experiment` and `game-db`.

- [ ] **Step 3: Play two sessions as yourself**

```bash
URL=$(databricks apps get agent-bricks-dm --profile brickbots -o json | jq -r .url)
TOKEN=$(databricks auth token --profile brickbots | jq -r .access_token) dm/scripts/smoke_turns.sh "$URL"
```
Expected:
- `SMOKE OK`, with 📚 lore events (the lore now works in deployment), 💾 state events, and `📍 delta-crossing`.
- Then Lakebase holds a new adventure whose `player_id` is a 64-character hash, not `smoke-player`:
```bash
cd dm && set -a && . ./.env && set +a && uv run python -c "
from agent.pgstore import connect_from_env
with connect_from_env() as c:
    print(c.execute('SELECT a.id, c.player_id, c.location_id, c.gold FROM rpg.adventures a JOIN rpg.characters c ON c.id=a.character_id ORDER BY a.updated_at DESC LIMIT 1').fetchone())"
```

- [ ] **Step 4: Check that the session store persists across a restart**

Restart the app with `databricks apps stop agent-bricks-dm --profile brickbots`, then `databricks apps start agent-bricks-dm --profile brickbots`. Then send one more turn in the **same** `SESSION`: re-run the script's `turn` function, or use a curl with the session ID it printed, asking `"Where am I and what have I got?"`.
Expected: the narration knows you're at the Delta Crossing with a lantern, and no `new_game` is needed.

- [ ] **Step 5: Distil and recall memories**

```bash
make memory-pipeline PROFILE=brickbots
cd dm && PIPE=$(agentbricks --profile brickbots memory pipeline list | grep dm-dreamer | awk '{print $1}') && \
  agentbricks --profile brickbots memory pipeline run "$PIPE"
```
Wait for the run to finish (`agentbricks memory pipeline get "$PIPE"` shows its last run). Then list entries:
`agentbricks --profile brickbots memory entries list --store <memory-store-id>`
Expected: at least one memory about the smoke adventure, such as buying a lantern from Marta or crossing to the Delta.

If the Dreamer produces nothing, check what the session store holds: `agentbricks --profile brickbots sessions items <session-id> --store <session-store>`. If the LangGraph checkpoints aren't transcript items the Dreamer can read, record that as a ruling and a finding. Then confirm memory instead through the model's `remember` tool: in a smoke turn, say "Remember that I promised Marta I'd find Keeper Aldric", check `memory entries list`, and then check the next session's 🧠 recall.

Then start a **new** session with `TOKEN=… dm/scripts/smoke_turns.sh "$URL"`.
Expected: the first turn shows `🧠 Memory: recalled N things about you`, and the narration nods to the earlier visit.

- [ ] **Step 6: Check that traces land in Unity Catalog**

```bash
databricks experimental aitools tools query --profile brickbots \
  "SELECT count(DISTINCT trace_id) AS traces, count(*) AS spans FROM serverless_stable_brickbots_catalog.databricks_adventure.dm_otel_spans"
```
Expected: the trace count has grown by at least 10 since the spike (two smoke runs of five turns).

- [ ] **Step 7: Record the evidence**

Record the outcomes of Steps 1–6 in the ledger: resource names, player ID length, restart continuity, memory entries, recalled count and trace counts.

---

### Task 7: Docs and spec deltas

**Files:**
- Modify: `README.md`, `dm/README.md`, `docs/superpowers/specs/2026-10-16-databricks-rpg-design.md`

- [ ] **Step 1: README updates**

In the root `README.md` deploy section, replace the paragraph under the code block with:
```markdown
This renders the lorebooks, deploys the bundle (schema, volume, AI Search endpoint, ingest job and the
Lakebase game database), migrates the game schema, builds the lore index, and then deploys the
Dungeon Master to Agent Runtime with its session and memory stores. Traces are stored in Unity
Catalog. Run `make memory-pipeline PROFILE=…` once to create the Dreamer that turns sessions into
long-term memories. `make destroy` removes it all. The AI Search endpoint bills while an index
exists, so destroy it when you're done.
```
In `dm/README.md`, add after the run instructions:
```markdown
Deploy with `make deploy-agent PROFILE=… CATALOG=…` from the repo root. It deploys from a clean copy
in `$TMPDIR`, because `agentbricks deploy` rewrites app.yaml and agent.toml with workspace-specific
values. Deployed calls need a bearer token: `TOKEN=$(databricks auth token -p <profile> | jq -r
.access_token) scripts/smoke_turns.sh <app-url>`. The node events are load_state → dm_reason →
tools → commit_state → compose. `scripts/lakebase_env.sh` needs `jq`.
```

- [ ] **Step 2: Spec deltas**

In the spec:
- **§2:** append the bullet `- **Deployed tracing (verified 2026-10-16):** Apps can't upload span artifacts to experiment storage, so the DM's experiment uses a Unity Catalog trace location (dm_* tables plus a SQL warehouse), with grants to the app service principal.`
- **§7, identity bullet:** replace it with `- **Identity:** player_id is the runtime's per-principal namespace hash (request_auth.namespace("player", "self")) from the Apps-forwarded identity. Client-supplied actors are ignored when deployed. Players only see and play their own saves (GameStore.owner).`
- **§7, Memory row:** append ` Recalled once at session start (top 5, a 🧠 event, injected into the DM prompt), plus the model's remember/recall tools. Populated by the Dreamer pipeline (make memory-pipeline).`
- **§13:** change step 4 to `4. make deploy-agent: clean build copy in $TMPDIR → agentbricks deploy → attach the game-db Lakebase resource → least-privilege grants (UC lore index and trace tables, Lakebase rpg schema, warehouse CAN_USE).`

- [ ] **Step 3: Commit**

```bash
git add README.md dm/README.md docs/superpowers/specs
git commit -m "docs: deployed DM, UC tracing, player identity and memory in README and spec

Co-authored-by: Isaac <no-reply@databricks.com>"
```

---

## Done when

- `make test` passes.
- `make deploy-agent PROFILE=brickbots CATALOG=serverless_stable_brickbots_catalog` deploys cleanly with 0 grant failures, and `git status` stays clean.
- An authenticated playthrough on the deployed DM shows lore, state and memory events, and the save is owned by the hashed player ID.
- A conversation continues after an app restart, and a new session recalls a memory distilled by the Dreamer.
- Traces from deployed turns appear in `dm_otel_spans`.
