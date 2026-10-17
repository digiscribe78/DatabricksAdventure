"""The DM's own Unity AI Gateway model service, where guardrail policies attach.

Policies apply to every account user of the service they're attached to, so they go on this
service, never on the shared system.ai models. Attaching them is a UI step (README).
"""

import json
import sys

from devtools.grants import _run

DESTINATION = "system.ai.databricks-claude-sonnet-4-5"


def service_name(catalog: str, schema: str) -> str:
    return f"{catalog}.{schema}.dm_model"


def create_body() -> dict:
    return {"comment": "Databricks Adventure: the Dungeon Master's model, where guardrail policies attach",
            "config": {"routing": {"destinations": [{
                "destination_type": "DESTINATION_TYPE_PAY_PER_TOKEN_FOUNDATION_MODEL",
                "name": DESTINATION,
                "pay_per_token_config": {"model": f"models/{DESTINATION}"},
                "traffic_percentage": 100}]}}}


def ensure_model_service(profile: str, catalog: str, schema: str, run=_run) -> bool:
    """Create dm_model if it doesn't exist. Returns True when it was created."""
    name = service_name(catalog, schema)
    try:
        run(["databricks", "ai-gateway", "get-model-service", f"model-services/{name}",
             "--profile", profile, "-o", "json"])
        return False
    except RuntimeError as e:
        if "not found" not in str(e).lower():
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
