# Databricks Adventure: one-command build, deploy and teardown.
# Usage: make deploy PROFILE=<databricks-profile> CATALOG=<uc-catalog>
PROFILE ?=
CATALOG ?=
SCHEMA ?= databricks_adventure
LAKEBASE_PROJECT ?= databricks-adventure
VOLUME = dbfs:/Volumes/$(CATALOG)/$(SCHEMA)/lore
INDEX = $(CATALOG).$(SCHEMA).lore_index
EVAL_MODEL ?= $(CATALOG).$(SCHEMA).dm_model
BUNDLE = databricks bundle --profile $(PROFILE) --var catalog=$(CATALOG) --var schema=$(SCHEMA)

.PHONY: content deploy ingest db deploy-agent deploy-app app-dev grant-player memory-pipeline test eval guardrails-check monitoring monitoring-stop destroy check-vars

check-vars:
	@test -n "$(PROFILE)" || (echo "Set PROFILE=<databricks-profile>" && exit 1)
	@test -n "$(CATALOG)" || (echo "Set CATALOG=<uc-catalog>" && exit 1)

content:
	cd pipelines && uv run python -m lore.render ../content/lore ../build/lore

deploy: check-vars content
	$(BUNDLE) deploy
	$(MAKE) db PROFILE=$(PROFILE)
	databricks fs cp --profile $(PROFILE) --recursive --overwrite build/lore $(VOLUME)/pdfs
	databricks fs cp --profile $(PROFILE) --overwrite content/manifest.yaml $(VOLUME)/manifest.yaml
	$(MAKE) ingest PROFILE=$(PROFILE) CATALOG=$(CATALOG) SCHEMA=$(SCHEMA)
	@echo "Lore index ready: $(INDEX). (For local DM dev only: put LORE_INDEX=$(INDEX) in dm/.env.)"
	$(MAKE) deploy-agent PROFILE=$(PROFILE) CATALOG=$(CATALOG) SCHEMA=$(SCHEMA)
	$(MAKE) deploy-app PROFILE=$(PROFILE)

ingest: check-vars
	$(BUNDLE) run ingest_lore
	@# A rebuilt index has no grants: give the DM its SELECT back.
	cd dm && DATABRICKS_CONFIG_PROFILE=$(PROFILE) uv run python -m devtools.lore_grant $(PROFILE) $(CATALOG) $(SCHEMA) $(WAREHOUSE)

db:
	@test -n "$(PROFILE)" || (echo "Set PROFILE=<databricks-profile>" && exit 1)
	env=$$(scripts/lakebase_env.sh $(PROFILE) $(LAKEBASE_PROJECT)) && eval "$$env" && cd dm && \
		DATABRICKS_CONFIG_PROFILE=$(PROFILE) uv run python -m agent.pgstore migrate ../content/npcs

deploy-agent: check-vars
	scripts/deploy_agent.sh $(PROFILE) $(CATALOG) $(SCHEMA)

memory-pipeline:
	@test -n "$(PROFILE)" || (echo "Set PROFILE=<databricks-profile>" && exit 1)
	cd dm && uv run python -m devtools.memory_pipeline $(PROFILE)

deploy-app:
	@test -n "$(PROFILE)" || (echo "Set PROFILE=<databricks-profile>" && exit 1)
	cd app && npm install --no-audit --no-fund && npm run build && \
		databricks bundle deploy --profile $(PROFILE) && databricks bundle run app --profile $(PROFILE)

app-dev:
	@test -n "$(PROFILE)" || (echo "Set PROFILE=<databricks-profile>" && exit 1)
	printf 'DM_URL=%s\nDM_DEV_TOKEN=%s\n' \
		"$$(databricks apps get agent-bricks-dm --profile $(PROFILE) -o json | jq -r .url)" \
		"$$(databricks auth token --profile $(PROFILE) | jq -r .access_token)" > app/.env
	cd app && DATABRICKS_CONFIG_PROFILE=$(PROFILE) npm run dev

grant-player:
	@test -n "$(PROFILE)" -a -n "$(PLAYER)" || (echo "Set PROFILE=… PLAYER=<user email>" && exit 1)
	for a in databricks-adventure agent-bricks-dm; do \
		databricks permissions update apps $$a --profile $(PROFILE) \
		  --json "{\"access_control_list\":[{\"user_name\":\"$(PLAYER)\",\"permission_level\":\"CAN_USE\"}]}" >/dev/null && echo "granted $$a"; done

test:
	cd pipelines && uv run pytest -q
	cd dm && uv run pytest -q

eval: check-vars
	cd dm && DATABRICKS_CONFIG_PROFILE=$(PROFILE) LORE_INDEX=$(INDEX) DM_MODEL=$(EVAL_MODEL) MLFLOW_DISABLE_AGENT_HINT=1 \
		uv run python -m evals.run

# Live monitoring: the eval judges score a sample of real games in dm-traces (MLflow production monitoring, Beta).
WAREHOUSE = $$(databricks experimental aitools tools get-default-warehouse --profile $(PROFILE) | tail -1 | tr -d '[:space:]')
monitoring:
	@test -n "$(PROFILE)" || (echo "Set PROFILE=<databricks-profile>" && exit 1)
	cd dm && DATABRICKS_CONFIG_PROFILE=$(PROFILE) MLFLOW_DISABLE_AGENT_HINT=1 uv run python -m devtools.monitoring $(WAREHOUSE)

monitoring-stop:
	@test -n "$(PROFILE)" || (echo "Set PROFILE=<databricks-profile>" && exit 1)
	cd dm && DATABRICKS_CONFIG_PROFILE=$(PROFILE) MLFLOW_DISABLE_AGENT_HINT=1 uv run python -m devtools.monitoring $(WAREHOUSE) stop

guardrails-check: check-vars
	cd dm && uv run python -m devtools.guardrails_check $(PROFILE) $(CATALOG) $(SCHEMA)

destroy: check-vars
	-cd app && databricks bundle destroy --auto-approve --profile $(PROFILE)
	-agentbricks --profile $(PROFILE) deployments delete agent-bricks-dm --yes
	-databricks vector-search-indexes delete-index --profile $(PROFILE) $(INDEX)
	$(BUNDLE) destroy --auto-approve
