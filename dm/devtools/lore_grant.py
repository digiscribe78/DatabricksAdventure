"""Re-grant the DM's SELECT on the lore index after an ingest.

Rebuilding the index (make ingest, or resuming after deleting it to stop billing) creates a new
object with no grants, and search_lore then fails for the DM's service principal. The first full
deploy grants it in deploy-agent; this keeps it after every rebuild.
"""

import sys

from devtools.grants import _cli, apply_uc_grants

APP = "agent-bricks-dm"


def lore_grant_statement(sp: str, catalog: str, schema: str) -> str:
    return f"GRANT SELECT ON TABLE `{catalog}`.`{schema}`.`lore_index` TO `{sp}`"


def regrant(catalog: str, schema: str, *, find_sp, apply) -> int:
    sp = find_sp()
    if sp is None:
        print(f"{APP} isn't deployed yet: deploy-agent grants it the lore index")
        return 0
    failures = apply([lore_grant_statement(sp, catalog, schema)])
    for f in failures:
        print(f"GRANT FAILED: {f}", file=sys.stderr)
    if not failures:
        print(f"{APP} can read {catalog}.{schema}.lore_index")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 4:
        print("usage: python -m devtools.lore_grant <profile> <catalog> <schema> <warehouse_id>", file=sys.stderr)
        return 2
    profile, catalog, schema, warehouse_id = args
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient(profile=profile)

    def find_sp():
        try:
            return _cli(profile, "apps", "get", APP).get("service_principal_client_id")
        except RuntimeError:
            return None  # no such app yet

    return regrant(catalog, schema, find_sp=find_sp,
                   apply=lambda stmts: apply_uc_grants(w, warehouse_id, stmts))


if __name__ == "__main__":
    raise SystemExit(main())
