# Databricks Adventure

A retro text RPG set in the Kingdom of Sparkia, where the Dungeon Master is an AI agent built on Databricks. While you play, the **Scrying Glass** panel shows what's happening behind the curtain: tool calls, retrieval, memory, state, guardrails and traces.

It's built to teach agent concepts on Databricks by playing.

> 🚧 Early days. Currently in design. See the [v1 design spec](docs/superpowers/specs/2026-10-16-databricks-rpg-design.md).

## Deploy (work in progress)

```bash
make deploy PROFILE=<your-databricks-profile> CATALOG=<a-catalog-you-can-create-schemas-in>
```

This renders the lorebooks, deploys the bundle (schema, volume, AI Search endpoint, ingest job and the
Lakebase game database), migrates the game schema, builds the lore index, and then deploys the
Dungeon Master to Agent Runtime with its session and memory stores. Traces are stored in Unity
Catalog. `make memory-pipeline PROFILE=…` creates a Dreamer pipeline for distilling sessions into
memories. `make destroy` removes it all. The AI Search endpoint bills while an index exists, so
destroy it when you're done.

## Licence

[Apache-2.0](LICENSE)
