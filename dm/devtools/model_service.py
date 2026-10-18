"""The DM's own Unity AI Gateway model service, where guardrail policies attach.

Policies apply to every account user of the service they're attached to, so they go on this
service, never on the shared system.ai models. Attaching them is a UI step (README).
"""

import json
import re
import sys

from devtools.grants import _run

DESTINATION = "system.ai.databricks-claude-sonnet-5"
# How the CLI says a model service is missing (seen live: "Resource not found"; the rest are its other forms).
_MISSING = re.compile(r"not found|does not exist|RESOURCE_DOES_NOT_EXIST|NOT_FOUND|\b404\b", re.IGNORECASE)


def service_name(catalog: str, schema: str) -> str:
    return f"{catalog}.{schema}.dm_model"


def create_body() -> dict:
    return {"comment": "Databricks Adventure: the Dungeon Master's model, where guardrail policies attach",
            "config": {"routing": {"destinations": [{
                "destination_type": "DESTINATION_TYPE_PAY_PER_TOKEN_FOUNDATION_MODEL",
                "name": DESTINATION,
                "pay_per_token_config": {"model": f"models/{DESTINATION}"},
                "traffic_percentage": 100}]}}}


def _destinations(got) -> list[str]:
    try:
        doc = json.loads(getattr(got, "stdout", "") or "{}")
    except ValueError:
        return []
    return [d.get("name", "") for d in doc.get("config", {}).get("routing", {}).get("destinations", [])]


def ensure_model_service(profile: str, catalog: str, schema: str, run=_run) -> bool:
    """Create dm_model if it doesn't exist, or repoint it at DESTINATION. Returns True when it was created.

    Repointing keeps the service, so the guardrail policies attached to it stay attached.
    """
    name = service_name(catalog, schema)
    try:
        got = run(["databricks", "ai-gateway", "get-model-service", f"model-services/{name}",
                   "--profile", profile, "-o", "json"])
        current = _destinations(got)
        if current and DESTINATION not in current:
            run(["databricks", "ai-gateway", "update-model-service", f"model-services/{name}",
                 "config.routing.destinations", "--json", json.dumps({"config": create_body()["config"]}),
                 "--profile", profile, "-o", "json"])
            print(f"model service {name}: repointed from {', '.join(current)} to {DESTINATION}")
        return False
    except RuntimeError as e:
        if not _MISSING.search(str(e)):
            raise
    run(["databricks", "ai-gateway", "create-model-service", f"schemas/{catalog}.{schema}", "dm_model",
         "--json", json.dumps(create_body()), "--profile", profile, "-o", "json"])
    return True


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3:
        print("usage: python -m devtools.model_service <profile> <catalog> <schema>", file=sys.stderr)
        return 2
    profile, catalog, schema = args
    created = ensure_model_service(profile, catalog, schema)
    print(f"model service {service_name(catalog, schema)}: {'created' if created else 'exists'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
