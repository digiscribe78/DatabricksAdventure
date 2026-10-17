-- Databricks Adventure game state (spec §7). Idempotent: safe to run on every deploy.
CREATE SCHEMA IF NOT EXISTS rpg;

CREATE TABLE IF NOT EXISTS rpg.characters (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id   text NOT NULL,
    name        text NOT NULL,
    archetype   text NOT NULL,
    might       int  NOT NULL,
    wits        int  NOT NULL,
    charm       int  NOT NULL,
    hp          int  NOT NULL,
    max_hp      int  NOT NULL,
    xp          int  NOT NULL DEFAULT 0,
    gold        int  NOT NULL,
    location_id text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rpg.inventory (
    character_id uuid NOT NULL REFERENCES rpg.characters (id) ON DELETE CASCADE,
    item_id      text NOT NULL,
    qty          int  NOT NULL CHECK (qty > 0),
    PRIMARY KEY (character_id, item_id)
);

CREATE TABLE IF NOT EXISTS rpg.quest_flags (
    character_id uuid NOT NULL REFERENCES rpg.characters (id) ON DELETE CASCADE,
    flag         text NOT NULL,
    value        text NOT NULL,
    PRIMARY KEY (character_id, flag)
);

CREATE TABLE IF NOT EXISTS rpg.adventures (
    id           text PRIMARY KEY,  -- the invocation session_id
    character_id uuid NOT NULL REFERENCES rpg.characters (id) ON DELETE CASCADE,
    status       text NOT NULL DEFAULT 'active',
    started_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rpg.npc_cards (
    npc_id           text PRIMARY KEY,
    name             text NOT NULL,
    persona          text NOT NULL,
    speech_style     text NOT NULL,
    secrets          text NOT NULL,
    home_location_id text NOT NULL
);

CREATE TABLE IF NOT EXISTS rpg.npc_disposition (
    character_id uuid NOT NULL REFERENCES rpg.characters (id) ON DELETE CASCADE,
    npc_id       text NOT NULL REFERENCES rpg.npc_cards (npc_id),
    disposition  int  NOT NULL CHECK (disposition BETWEEN -3 AND 3),
    PRIMARY KEY (character_id, npc_id)
);

CREATE INDEX IF NOT EXISTS characters_player_idx ON rpg.characters (player_id);

ALTER TABLE rpg.adventures ADD COLUMN IF NOT EXISTS client_session_id text;
ALTER TABLE rpg.npc_cards ADD COLUMN IF NOT EXISTS reveal_after text;
