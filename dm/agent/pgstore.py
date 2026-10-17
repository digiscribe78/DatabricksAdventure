"""GameStore on Lakebase Postgres. Each method is one connection and one transaction.

Connection settings come from PGHOST/PGPORT/PGDATABASE/PGUSER/LAKEBASE_ENDPOINT, which is the same
contract Databricks Apps inject for a Lakebase resource. The password is a short-lived OAuth token.
"""

import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Callable

import psycopg
from databricks_agentkit import workspace_client

from rpg.state import GameState, NpcCard, NpcPresence
from rpg.store import STAT_KEYS, load_npc_cards
from rpg.world import START_LOCATION_ID, Character, new_character

SCHEMA_SQL = (Path(__file__).resolve().parents[1] / "rpg" / "schema.sql").read_text()
TOKEN_TTL_S = 45 * 60  # tokens last 1 hour; refresh well before
_token_cache: dict = {"token": None, "at": 0.0}


def lakebase_token() -> str:
    now = time.time()
    if _token_cache["token"] is None or now - _token_cache["at"] >= TOKEN_TTL_S:
        cred = workspace_client().postgres.generate_database_credential(endpoint=os.environ["LAKEBASE_ENDPOINT"])
        _token_cache.update(token=cred.token, at=now)
    return _token_cache["token"]


def connect_from_env() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ["PGHOST"], port=int(os.getenv("PGPORT", "5432")), dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"], password=lakebase_token(), sslmode="require", connect_timeout=10,
    )


def migrate(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_SQL)


_CHAR_COLS = "c.id, c.name, c.archetype, c.might, c.wits, c.charm, c.hp, c.max_hp, c.xp, c.gold, c.location_id"


class PostgresStore:
    def __init__(self, connect: Callable[[], psycopg.Connection]):
        self._connect = connect

    @classmethod
    def from_env(cls) -> "PostgresStore":
        return cls(connect_from_env)

    def seed_npcs(self, cards: list[NpcCard]) -> None:
        with self._connect() as conn:
            for c in cards:
                conn.execute(
                    "INSERT INTO rpg.npc_cards (npc_id, name, persona, speech_style, secrets, home_location_id, reveal_after) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (npc_id) DO UPDATE SET name = EXCLUDED.name, "
                    "persona = EXCLUDED.persona, speech_style = EXCLUDED.speech_style, secrets = EXCLUDED.secrets, "
                    "home_location_id = EXCLUDED.home_location_id, reveal_after = EXCLUDED.reveal_after",
                    (c.npc_id, c.name, c.persona, c.speech_style, c.secrets, c.home_location_id, c.reveal_after),
                )

    def create_adventure(self, session_id, player_id, name, archetype, client_session_id=None):
        c = new_character(name, archetype)
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM rpg.adventures WHERE id = %s", (session_id,)).fetchone():
                raise ValueError(f"adventure already exists for session {session_id}")
            (cid,) = conn.execute(
                "INSERT INTO rpg.characters (player_id, name, archetype, might, wits, charm, hp, max_hp, xp, gold, "
                "location_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (player_id, c.name, c.archetype, c.might, c.wits, c.charm, c.hp, c.max_hp, c.xp, c.gold,
                 START_LOCATION_ID),
            ).fetchone()
            self._write_inventory(conn, cid, c.inventory)
            conn.execute("INSERT INTO rpg.adventures (id, character_id, client_session_id) VALUES (%s, %s, %s)",
                         (session_id, cid, client_session_id))
            conn.execute("INSERT INTO rpg.adventure_stats (adventure_id) VALUES (%s)", (session_id,))
        return self.load(session_id)

    def load(self, session_id):
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT {_CHAR_COLS} FROM rpg.adventures a JOIN rpg.characters c ON c.id = a.character_id "
                "WHERE a.id = %s", (session_id,),
            ).fetchone()
            if row is None:
                return None
            cid, name, archetype, might, wits, charm, hp, max_hp, xp, gold, location_id = row
            inventory = [item for item, qty in conn.execute(
                "SELECT item_id, qty FROM rpg.inventory WHERE character_id = %s ORDER BY item_id", (cid,)
            ).fetchall() for _ in range(qty)]
            flags = dict(conn.execute("SELECT flag, value FROM rpg.quest_flags WHERE character_id = %s", (cid,)).fetchall())
            npcs = [
                NpcPresence(npc_id=r[0], name=r[1], persona=r[2], speech_style=r[3], secrets=r[4],
                            home_location_id=r[5], disposition=r[6], reveal_after=r[7])
                for r in conn.execute(
                    "SELECT n.npc_id, n.name, n.persona, n.speech_style, n.secrets, n.home_location_id, "
                    "COALESCE(d.disposition, 0), n.reveal_after FROM rpg.npc_cards n LEFT JOIN rpg.npc_disposition d "
                    "ON d.npc_id = n.npc_id AND d.character_id = %s WHERE n.home_location_id = %s ORDER BY n.npc_id",
                    (cid, location_id),
                ).fetchall()
            ]
        character = Character(name=name, archetype=archetype, might=might, wits=wits, charm=charm, hp=hp,
                              max_hp=max_hp, xp=xp, gold=gold, inventory=inventory)
        return GameState(character=character, location_id=location_id, flags=flags, npcs=npcs)

    def owner(self, session_id):
        with self._connect() as conn:
            row = conn.execute("SELECT c.player_id FROM rpg.adventures a JOIN rpg.characters c ON c.id = a.character_id "
                               "WHERE a.id = %s", (session_id,)).fetchone()
        return row[0] if row else None

    def commit(self, session_id, state):
        c = state.character
        with self._connect() as conn:
            found = conn.execute("SELECT character_id FROM rpg.adventures WHERE id = %s", (session_id,)).fetchone()
            if found is None:
                raise LookupError(f"no adventure for session {session_id}")
            (cid,) = found
            conn.execute("UPDATE rpg.characters SET hp = %s, xp = %s, gold = %s, location_id = %s WHERE id = %s",
                         (c.hp, c.xp, c.gold, state.location_id, cid))
            conn.execute("DELETE FROM rpg.inventory WHERE character_id = %s", (cid,))
            self._write_inventory(conn, cid, c.inventory)
            for flag, value in state.flags.items():
                conn.execute("INSERT INTO rpg.quest_flags (character_id, flag, value) VALUES (%s, %s, %s) "
                             "ON CONFLICT (character_id, flag) DO UPDATE SET value = EXCLUDED.value", (cid, flag, value))
            for npc in state.npcs:
                conn.execute("INSERT INTO rpg.npc_disposition (character_id, npc_id, disposition) VALUES (%s, %s, %s) "
                             "ON CONFLICT (character_id, npc_id) DO UPDATE SET disposition = EXCLUDED.disposition",
                             (cid, npc.npc_id, npc.disposition))
            conn.execute("UPDATE rpg.adventures SET updated_at = now() WHERE id = %s", (session_id,))

    def add_stats(self, session_id, counts):
        # Column names come only from STAT_KEYS, never from input, so building the SQL is safe.
        cols = [k for k in STAT_KEYS if counts.get(k)]
        if not cols:
            return
        values = [int(counts[k]) for k in cols]
        sets = ", ".join(f"{k} = rpg.adventure_stats.{k} + EXCLUDED.{k}" for k in cols)
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO rpg.adventure_stats (adventure_id, since_start, {', '.join(cols)}) "
                f"VALUES (%s, false, {', '.join(['%s'] * len(cols))}) "
                f"ON CONFLICT (adventure_id) DO UPDATE SET {sets}, updated_at = now()",
                (session_id, *values),
            )

    def stats(self, session_id):
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT {', '.join(STAT_KEYS)}, since_start FROM rpg.adventure_stats WHERE adventure_id = %s",
                (session_id,),
            ).fetchone()
        return None if row is None else {**dict(zip(STAT_KEYS, row[:-1])), "since_start": row[-1]}

    def list_adventures(self, player_id):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT a.id, c.name, c.archetype, c.location_id, a.status, a.client_session_id FROM rpg.adventures a "
                "JOIN rpg.characters c ON c.id = a.character_id WHERE c.player_id = %s ORDER BY a.updated_at DESC",
                (player_id,),
            ).fetchall()
        return [dict(zip(("session_id", "name", "archetype", "location_id", "status", "client_session_id"), r)) for r in rows]

    def delete_adventure(self, session_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM rpg.characters WHERE id = (SELECT character_id FROM rpg.adventures WHERE id = %s)",
                         (session_id,))

    @staticmethod
    def _write_inventory(conn, cid, inventory: list[str]) -> None:
        for item, qty in Counter(inventory).items():
            conn.execute("INSERT INTO rpg.inventory (character_id, item_id, qty) VALUES (%s, %s, %s)", (cid, item, qty))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or args[0] != "migrate":
        print("usage: python -m agent.pgstore migrate <npcs_dir>", file=sys.stderr)
        return 2
    with connect_from_env() as conn:
        migrate(conn)
    cards = load_npc_cards(args[1])
    PostgresStore.from_env().seed_npcs(cards)
    print(f"migrated schema rpg and seeded {len(cards)} NPC cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
