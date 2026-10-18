# Architecture

How the pieces of Databricks Adventure fit together. GitHub renders these diagrams from the Mermaid text, so edit them here when the architecture changes.

## The system

```mermaid
flowchart LR
  player(["Player<br/>(browser)"])

  subgraph apps["Databricks Apps"]
    game["Game app<br/>databricks-adventure<br/>AppKit + React<br/>Scrying Glass · Guide · map"]
    subgraph runtime["Agent Runtime: agent-bricks-dm"]
      dm["Dungeon Master<br/>LangGraph agent"]
    end
  end

  subgraph gateway["Unity AI Gateway"]
    model["dm_model<br/>model service"]
    policy{{"stay_in_sparkia<br/>service policy"}}
    llm["system.ai<br/>Claude Sonnet 5"]
  end

  subgraph data["Unity Catalog and Lakebase"]
    lorebooks[/"Lorebook PDFs<br/>UC volume"/]
    index[("AI Search<br/>lore_index")]
    lake[("Lakebase Postgres<br/>rpg: characters, flags,<br/>NPCs, adventure_stats")]
  end

  subgraph memory["Agent Bricks memory"]
    sessions[("Session store<br/>LangGraph checkpoints")]
    transcripts[("Transcript store<br/>plain messages")]
    dreamer[["Dreamer pipeline<br/>scheduled"]]
    mem[("Memory store<br/>long-term memories")]
  end

  subgraph mlflow["MLflow"]
    traces[("dm-traces<br/>traces in Unity Catalog")]
    evals[("dm-evals<br/>make eval report cards")]
    judges[["Live monitoring<br/>safety · in_character ·<br/>player_agency"]]
  end

  lorebooks -- "parse, chunk<br/>(ingest job)" --> index

  player <-- "turns, streamed events" --> game
  game <-- "invocations<br/>(on behalf of the user)" --> dm
  dm -- "model calls" --> model
  model --> policy
  policy -- "allowed" --> llm
  dm -- "search_lore" --> index
  dm <-- "load / commit state, stats" --> lake
  dm <-- "checkpoint" --> sessions
  dm -- "each turn" --> transcripts
  transcripts --> dreamer --> mem
  mem -- "recall at the start<br/>of an adventure" --> dm
  dm -- "every turn traced" --> traces
  judges -- "score a sample" --> traces
  evals -. "28 seeded scenarios<br/>played in-process" .-> dm
```

## One turn

```mermaid
sequenceDiagram
  autonumber
  participant P as Player
  participant G as Game app
  participant D as DM (LangGraph)
  participant L as Lakebase
  participant M as dm_model (AI Gateway)
  participant T as Tools
  participant S as AI Search

  P->>G: "I attack the swamp rat"
  G->>D: invocation
  D->>L: load_state (save, flags, NPCs)
  D-->>G: game snapshot (scene, sheet, map shown at once)
  D->>M: dm_reason
  Note over M: stay_in_sparkia screens the player's words.<br/>A block becomes an in-world refusal (🛡).
  M-->>D: tool calls
  D->>T: roll_check / resolve_attack / move_to / …
  D->>S: search_lore (📚)
  T-->>D: results (code does the maths)
  D->>L: commit_state, one transaction (💾)
  D->>M: compose: narration + 2–4 choices
  M-->>D: ComposeOutput, validated
  D-->>G: turn: narration, choices, events
  G-->>P: the turn, and the Scrying Glass lights up
  D->>L: add_stats (what you just saw)
  D->>D: transcript written, for the Dreamer
```

## Where to read more

- The DM's graph: `dm/agent/dm_graph.py`
- Tools: `dm/agent/tools/`
- Guardrails: `dm/agent/guardrails.py` and `content/guardrails/stay-in-sparkia.md`
- Memory: `dm/agent/transcripts.py` and `dm/agent/memory.py`
- Evals and monitoring: `dm/evals/` and `dm/devtools/monitoring.py`
- The game app: `app/`
