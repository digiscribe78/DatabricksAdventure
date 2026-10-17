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

.PHONY: content deploy ingest db deploy-agent deploy-app app-dev grant-player memory-pipeline test eval guardrails-check destroy check-vars

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
	@echo "Lore index ready: $(INDEX). Put LORE_INDEX=$(INDEX) in dm/.env"
	$(MAKE) deploy-agent PROFILE=$(PROFILE) CATALOG=$(CATALOG) SCHEMA=$(SCHEMA)
	$(MAKE) deploy-app PROFILE=$(PROFILE)

ingest: check-vars
	$(BUNDLE) run ingest_lore

db:
	@test -n "$(PROFILE)" || (echo "Set PROFILE=<databricks-profile>" && exit 1)
	eval "$$(scripts/lakebase_env.sh $(PROFILE) $(LAKEBASE_PROJECT))" && cd dm && \
		DATABRICKS_CONFIG_PROFILE=$(PROFILE) uv run python -m agent.pgstore migrate ../content/npcs

deploy-agent: check-vars
	scripts/deploy_agent.sh $(PROFILE) $(CATALOG) $(SCHEMA)

memory-pipeline:
	@test -n "$(PROFILE)" || (echo "Set PROFILE=<databricks-profile>" && exit 1)
	cd dm && STORE=$$(grep -A1 '^\[memory_store\]' agent.toml | sed -n 's/name = "\(.*\)"/\1/p') && \
	SESS=$$(grep -A1 '^\[session_store\]' agent.toml | sed -n 's/name = "\(.*\)"/\1/p') && \
	(COLUMNS=250 agentbricks --profile $(PROFILE) memory pipeline list | grep -q "$$STORE" || \
	 agentbricks --profile $(PROFILE) memory pipeline create --memory-store $$STORE --session-store $$SESS \
	   --display-name dm-dreamer --instructions @../content/dreamer-instructions.md --trigger manual)

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

guardrails-check: check-vars
	cd dm && uv run python -m devtools.guardrails_check $(PROFILE) $(CATALOG) $(SCHEMA)

destroy: check-vars
	-cd app && databricks bundle destroy --auto-approve --profile $(PROFILE)
	-agentbricks --profile $(PROFILE) deployments delete agent-bricks-dm --yes
	-databricks vector-search-indexes delete-index --profile $(PROFILE) $(INDEX)
	$(BUNDLE) destroy --auto-approve
