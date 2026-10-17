# Databricks Adventure: M5b Memory That Learns From Play

- **Date:** 2026-10-17
- **Status:** Approved; implemented in M5b
- **Parent spec:** `2026-10-16-databricks-rpg-design.md` §7 (state and memory). This refines M3b's memory wiring; where they differ, this one wins.
- **Platform reference:** Databricks docs, "Stateful agents" and "Tutorial: Add sessions and memory to an existing agent" (Agent Bricks sessions and memory, Beta).

## 1. Intent

| Decision | Choice |
|---|---|
| Purpose | Make long-term memory work the way the platform intends for a LangGraph agent: memories are distilled from what happened in play, not only from what the DM chooses to `remember`. |
| The gap | The Dreamer pipeline `dm-dreamer` reads `dm-vhiyme-sessions`, the LangGraph checkpointer's store. Its items are msgpack-encoded checkpoint blobs, not messages, so the pipeline has nothing it can read. Today every memory comes from the DM's `remember` tool. The tutorial says LangGraph agents need a separate transcript store. |
| Distilling | Both platform paths. The **scheduled Dreamer pipeline** reads the new transcript store, and when an adventure ends (victory or defeat), a **synchronous `extract_memories`** call on that session means a player who finishes and starts again is remembered straight away. |
| Unchanged | The checkpointer (`dm-vhiyme-sessions`), `memory_tools` (`remember`/`recall`), recall at the start of a game into the system prompt, per-`actor_id` scoping. |

## 2. The transcript store

- **Name:** the checkpointer store's name with `-sessions` replaced by `-transcripts` (today `dm-vhiyme-transcripts`), derived from `agent.toml` `[session_store]`.
- **Deploy:** `devtools/transcripts_store.py` idempotently creates the store (`AgentKitClient.session_stores.create`) if it's missing, and grants the DM's service principal `WRITE` (`grant_permission`). It runs from `scripts/deploy_agent.sh`. The deployed env gains `TRANSCRIPT_STORE=<name>`.
- **Scoping:** each transcript session uses the same `actor_id` and `session_id` as the checkpointer thread, so the pipeline writes memories to the right player.

## 3. Recording turns: `agent/transcripts.py`

```python
def record_turn(actor: str, session_id: str, player_text: str | None, reply: str, invocation_id: str | None,
                client=None) -> None:
```

- Gets the transcript session, or adds it (`store.add(actor_id=…, session_id=…)`), then appends plain items in the tutorial's shape:
  - `{"type": "message", "role": "user", "content": player_text, "invocation_id": …}`, only when there is player text;
  - `{"type": "message", "role": "assistant", "content": reply, "invocation_id": …}`. The reply is the narration plus its choices.
- **De-duplication:** before appending, it reads the newest item. If that item's `invocation_id` matches, the turn was already recorded (a recovery replay) and nothing is written.
- **Never breaks a turn:** any failure is logged and swallowed. If `TRANSCRIPT_STORE` is unset (local dev, tests), it does nothing.

**Called from** `runtime/adapter.py` `_invoke_agent`, after the turn has been streamed and the `game` snapshot emitted:
- **Player text:** the content of the invocation's last user message.
  - It is `None` for the opening scene and for a resume with no message.
  - On a **blocked turn** (the turn has a `guardrail` event), it is replaced with `REFUSED_PLACEHOLDER`, so blocked words never reach the transcript, the pipeline or memory.
- **Reply:** `turn["narration"]` plus `- choice` lines.

## 4. Distilling at the end of an adventure

When `turn["game_over"]` is set, the adapter calls `distil_adventure(actor, session_id, client=None) -> list[str]` (in `agent/transcripts.py`). It calls:

```python
session.extract_memories(memory_store=<AGENT_MEMORY_STORE>, instructions=<content/dreamer-instructions.md>)
```

and returns the new entries' `content`.

- The list is added to the returned and emitted `game` snapshot as `distilled`. M8's end screen shows it as the 🧠 recap; M5b adds no UI.
- Failures are logged and give `[]`.
- The Dreamer instructions file is copied into the deployed build, so the instructions are the same for the pipeline and the end-of-game call.

## 5. The Dreamer pipeline

`make memory-pipeline PROFILE=…` ensures exactly one pipeline, `dm-dreamer`, with:
- `--session-store <transcripts store>`;
- `--memory-store <memory store>`;
- `--trigger scheduled`;
- `--instructions @../content/dreamer-instructions.md`.

A pipeline's session store can't be changed with `update`, so any existing pipeline on the old store is deleted first and then recreated. The model can't be chosen: on 2026-10-17 the service ignored `--model` on create and rejected it on update ("unsupported update path: model"), so distilling uses the platform's default model. `scheduled` runs about every 24 hours. This is implemented in `devtools/memory_pipeline.py` and replaces the inline shell in the Makefile.

## 6. Recall through the SDK

`agent/memory.py` `recall_memories` uses `AgentKitClient(workspace_client()).memory_stores.get(store).search(actor_id=…, query=…, limit=…)` and returns each result's `.memory.content`. This shape was verified live on 2026-10-17. It replaces the raw `POST /api/2.0/agents/memory-stores/{store}/entries:search`, and the behaviour is unchanged.

## 7. Testing

- **Offline,** with a fake AgentKit client:
  - item shapes;
  - no user item on cue turns;
  - the placeholder on blocked turns;
  - de-duplication on replay;
  - failures swallowed;
  - unset `TRANSCRIPT_STORE` is a no-op;
  - `distil_adventure` returns contents and swallows failures;
  - the adapter records every turn and distils only when `game_over`;
  - `recall_memories` maps search results;
  - `transcripts_store` create/grant is idempotent;
  - `memory_pipeline` deletes a pipeline on the wrong store and creates the right one.
- **Live:**
  1. Deploy.
  2. Play a short game to an ending (the campaign smoke, or a quick defeat).
  3. `agentbricks sessions items list --store dm-vhiyme-transcripts --session-id <id>` shows plain user and assistant messages.
  4. The final `game` payload has `distilled`.
  5. `agentbricks memory pipeline run` on the new pipeline completes.
  6. A new game's first turn shows 🧠 recalling a distilled memory.

## 8. Live results (2026-10-17)

- **Transcripts:** a smoke game wrote 13 plain items: the opening narration, a user and assistant pair per turn, and the jailbreak turn as the placeholder.
- **Dreamer:** a manual run distilled a new memory from the transcript, "Plays a character named Tess… Promised Marta Quill… now trusts Tess more", and a new game's opening recalled it ("recalled 2 things about you").
  - The run's API `stats` reported zeros, but the job logs showed `actors_processed: 1, entries_written: 1`. The job logs are the source of truth.
- **End-of-game extraction** (`extract_memories`) currently fails on this workspace with `ai-gateway upstream error status 403`, even on a two-message test session.
  - The service calls a fixed model (`system.ai.claude-sonnet-5`) through AI Gateway, and the same user can query that model directly.
  - So the failure is inside the extraction service, not our access. The code logs it and returns `[]`, so finished adventures are distilled by the next Dreamer run instead.
  - It is kept as-is so it starts working when the service does.

## 9. Out of scope

- The end-screen UI for `distilled` (M8).
- Backfilling transcripts for past games: their checkpoints can't be read as messages.
- Deleting or editing memories from the game.
