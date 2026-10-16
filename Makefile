# Databricks Adventure: one-command build, deploy and teardown.
# Usage: make deploy PROFILE=<databricks-profile> CATALOG=<uc-catalog>
PROFILE ?=
CATALOG ?=
SCHEMA ?= databricks_adventure
LAKEBASE_PROJECT ?= databricks-adventure
VOLUME = dbfs:/Volumes/$(CATALOG)/$(SCHEMA)/lore
INDEX = $(CATALOG).$(SCHEMA).lore_index
BUNDLE = databricks bundle --profile $(PROFILE) --var catalog=$(CATALOG) --var schema=$(SCHEMA)

.PHONY: content deploy ingest db test destroy check-vars

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

ingest: check-vars
	$(BUNDLE) run ingest_lore

db:
	@test -n "$(PROFILE)" || (echo "Set PROFILE=<databricks-profile>" && exit 1)
	eval "$$(scripts/lakebase_env.sh $(PROFILE) $(LAKEBASE_PROJECT))" && cd dm && \
		DATABRICKS_CONFIG_PROFILE=$(PROFILE) uv run python -m agent.pgstore migrate ../content/npcs

test:
	cd pipelines && uv run pytest -q
	cd dm && uv run pytest -q

destroy: check-vars
	-databricks vector-search-indexes delete-index --profile $(PROFILE) $(INDEX)
	$(BUNDLE) destroy --auto-approve
