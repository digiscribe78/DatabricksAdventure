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
[[ "$WAREHOUSE" =~ ^[0-9a-f]+$ ]] || { echo "Could not find a default SQL warehouse (got '$WAREHOUSE')" >&2; exit 1; }
echo "warehouse: $WAREHOUSE"
cd "$ROOT/dm"
DATABRICKS_CONFIG_PROFILE="$PROFILE" uv run python -m devtools.tracing "$CATALOG" "$SCHEMA" "$WAREHOUSE"
DATABRICKS_CONFIG_PROFILE="$PROFILE" uv run python -m devtools.model_service "$PROFILE" "$CATALOG" "$SCHEMA"
DATABRICKS_CONFIG_PROFILE="$PROFILE" uv run python -m devtools.transcripts_store "$PROFILE"
TRANSCRIPTS=$(uv run python -c "from agent.transcripts import transcript_store_name; print(transcript_store_name())")
uv run python -m devtools.build "$ROOT/dm" "$OUT" \
  "MLFLOW_TRACING_SQL_WAREHOUSE_ID=$WAREHOUSE" "LORE_INDEX=$CATALOG.$SCHEMA.lore_index" "LAKEBASE_ENDPOINT=$EP" "DM_MODEL=$CATALOG.$SCHEMA.dm_model" "TRANSCRIPT_STORE=$TRANSCRIPTS"
cp "$ROOT/content/dreamer-instructions.md" "$OUT/dreamer-instructions.md"
(cd "$OUT" && agentbricks --profile "$PROFILE" deploy dm --allow-user-scope-update)
LB_ENV=$("$ROOT/scripts/lakebase_env.sh" "$PROFILE")  # assigned first so a failure trips set -e
eval "$LB_ENV"
grants_rc=0
DATABRICKS_CONFIG_PROFILE="$PROFILE" uv run python -m devtools.grants "$PROFILE" "$APP" "$CATALOG" "$SCHEMA" "$WAREHOUSE" \
  || grants_rc=$?
# Always roll out: the game-db resource only reaches the running app on the next deployment.
(cd "$OUT" && agentbricks --profile "$PROFILE" deploy dm)
if [ "$grants_rc" -ne 0 ]; then
  echo "Deployed $APP, but some grants FAILED (see above). Fix them and re-run make deploy-agent." >&2
  exit "$grants_rc"
fi
echo "Deployed $APP. Check: git status (tracked files must be unchanged)."
