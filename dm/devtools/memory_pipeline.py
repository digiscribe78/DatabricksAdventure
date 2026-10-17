"""make memory-pipeline: exactly one Dreamer, dm-dreamer, distilling the transcript store.

A pipeline's session store can't be changed in place, so one left on the checkpointer's store
(msgpack blobs it can't read) is deleted and recreated.
"""

import json
import sys
import tomllib
from pathlib import Path

from devtools.grants import _run

DISPLAY_NAME = "dm-dreamer"
MODEL = "system.ai.claude-sonnet-4-5"
INSTRUCTIONS = "@../content/dreamer-instructions.md"


def plan(pipelines: list[dict], memory_store: str, transcript_store: str) -> tuple[list[str], bool]:
    ours = [p for p in pipelines
            if p.get("display_name") == DISPLAY_NAME and p.get("memory_store") == f"memory-stores/{memory_store}"]
    keep = [p for p in ours if p.get("session_store") == f"session-stores/{transcript_store}"]
    return [p["name"] for p in ours if p not in keep], not keep


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m devtools.memory_pipeline <profile>", file=sys.stderr)
        return 2
    profile = args[0]
    from databricks.sdk import WorkspaceClient

    from agent.transcripts import AGENT_TOML, transcript_store_name

    memory_store = tomllib.loads(Path(AGENT_TOML).read_text())["memory_store"]["name"]
    transcripts = transcript_store_name()
    listed = WorkspaceClient(profile=profile).api_client.do("GET", "/api/2.0/agents/memory-pipelines")
    delete, create = plan(listed.get("memory_pipelines") or [], memory_store, transcripts)
    for name in delete:
        _run(["agentbricks", "--profile", profile, "memory", "pipeline", "delete", name])
        print(f"deleted {name} (it read the checkpoint store)")
    if create:
        _run(["agentbricks", "--profile", profile, "memory", "pipeline", "create", "--memory-store", memory_store,
              "--session-store", transcripts, "--display-name", DISPLAY_NAME, "--model", MODEL,
              "--instructions", INSTRUCTIONS, "--trigger", "scheduled"])
        print(f"created {DISPLAY_NAME} on {transcripts}")
    else:
        print(f"{DISPLAY_NAME} already distils {transcripts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
