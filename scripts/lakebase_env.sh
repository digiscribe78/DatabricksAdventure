#!/usr/bin/env bash
# Print export lines for connecting to the game's Lakebase project as the current user.
# Usage: eval "$(scripts/lakebase_env.sh <profile> [project_id])"
set -euo pipefail
PROFILE="$1"; PROJECT="${2:-databricks-adventure}"
EP="projects/$PROJECT/branches/production/endpoints/primary"
HOST=$(databricks postgres get-endpoint "$EP" --profile "$PROFILE" -o json | jq -r '.status.hosts.host')
USER_NAME=$(databricks current-user me --profile "$PROFILE" -o json | jq -r '.userName')
echo "export PGHOST=$HOST PGPORT=5432 PGDATABASE=databricks_postgres PGUSER=$USER_NAME LAKEBASE_ENDPOINT=$EP"
