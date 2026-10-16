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
