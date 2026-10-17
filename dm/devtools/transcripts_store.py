"""The DM's transcript session store, which the Dreamer pipeline distils (see agent/transcripts.py)."""

import sys


def ensure_store(client, name: str) -> bool:
    """Create the store if it's missing. Returns True when it was created."""
    try:
        client.session_stores.get(name)
        return False
    except Exception:  # noqa: BLE001 - not found
        client.session_stores.create(name, description="Databricks Adventure: turn transcripts for the Dreamer")
        return True


def grant_store(client, name: str, sp: str) -> None:
    client.session_stores.get(name).grant_permission(sp, permission="WRITE")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m devtools.transcripts_store <profile>", file=sys.stderr)
        return 2
    from databricks.sdk import WorkspaceClient
    from databricks_agentkit import AgentKitClient

    from agent.transcripts import transcript_store_name

    name = transcript_store_name()
    created = ensure_store(AgentKitClient(WorkspaceClient(profile=args[0])), name)
    print(f"transcript store {name}: {'created' if created else 'exists'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
