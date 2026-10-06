import os
from contextvars import ContextVar
from datetime import datetime

import psycopg2
from pgvector.psycopg2 import register_vector
from chromadb.utils import embedding_functions

EMBEDDING_DIM = 384

# Firebase UID of the signed-in user on whose behalf the current request/task runs.
# Set by main.py after token verification. ContextVars propagate into asyncio tasks
# and asyncio.to_thread(), so Brain code doesn't need to pass the user through every call.
# When unset (None) memory is neither read nor written: no data without a known owner.
current_user_id: ContextVar = ContextVar("current_user_id", default=None)


class Memory:
    def __init__(self):
        self.conn_string = os.getenv("SUPABASE_DB_URL")
        self._embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        self.conn = None
        self._db_ready = False
        try:
            self._connect()
            self._init_db()
            self._db_ready = True
        except Exception as e:
            # Don't let a startup DB hiccup take down the whole app — memory
            # degrades gracefully (chat still works, just without persistence)
            # and every public method below retries the connection on next use.
            print(f"[Memory] could not connect at startup, will retry on first use: {e}")

    def _connect(self):
        self.conn = psycopg2.connect(self.conn_string, sslmode="require", connect_timeout=10)
        self.conn.autocommit = True
        register_vector(self.conn)

    def _ensure_connection(self):
        """Returns True if the connection is usable, False if unreachable (caller should degrade gracefully)."""
        if self.conn is not None:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return True
            except Exception:
                pass
        try:
            self._connect()
            if not self._db_ready:
                self._init_db()
                self._db_ready = True
            return True
        except Exception as e:
            print(f"[Memory] connection unavailable: {e}")
            return False

    def _embed(self, text: str):
        return self._embedding_fn([text])[0]

    def _init_db(self):
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ DEFAULT now(),
                    user_input TEXT,
                    assistant_response TEXT,
                    embedding VECTOR({EMBEDDING_DIM})
                )
            """)
            # Per-user ownership (added for privacy / data-deletion requests).
            # Rows saved before this column existed keep user_id NULL and are never shown to any user.
            cur.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS user_id TEXT")
            cur.execute("CREATE INDEX IF NOT EXISTS conversations_user_id_idx ON conversations (user_id)")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

    def get_last_reflection_time(self):
        if not self._ensure_connection():
            return None
        with self.conn.cursor() as cur:
            cur.execute("SELECT value FROM app_state WHERE key = 'last_reflection_at'")
            row = cur.fetchone()
            return row[0] if row else None

    def set_last_reflection_time(self, iso_timestamp: str):
        if not self._ensure_connection():
            return
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_state (key, value) VALUES ('last_reflection_at', %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (iso_timestamp,)
            )

    def get_last_securebot_alert_ts(self):
        if not self._ensure_connection():
            return None
        with self.conn.cursor() as cur:
            cur.execute("SELECT value FROM app_state WHERE key = 'last_securebot_alert_ts'")
            row = cur.fetchone()
            return float(row[0]) if row else None

    def set_last_securebot_alert_ts(self, ts: float):
        if not self._ensure_connection():
            return
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_state (key, value) VALUES ('last_securebot_alert_ts', %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (str(ts),)
            )

    def save(self, user_input: str, response: str):
        uid = current_user_id.get()
        if not uid or not self._ensure_connection():
            return
        embedding = self._embed(f"User: {user_input}\nJOESTAR: {response}")
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (user_input, assistant_response, embedding, user_id) VALUES (%s, %s, %s, %s)",
                (user_input, response, embedding, uid)
            )

    def delete_user_data(self) -> int:
        """Erase every stored conversation belonging to the current user. Returns rows deleted."""
        uid = current_user_id.get()
        if not uid:
            return 0
        if not self._ensure_connection():
            raise RuntimeError("Memory database unavailable")
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM conversations WHERE user_id = %s", (uid,))
            return cur.rowcount

    def get_recent(self, n=5) -> list:
        """Get the n most recent exchanges, oldest first."""
        uid = current_user_id.get()
        if not uid or not self._ensure_connection():
            return []
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT user_input, assistant_response FROM conversations WHERE user_id = %s ORDER BY id DESC LIMIT %s",
                (uid, n)
            )
            rows = cur.fetchall()
        return list(reversed(rows))

    def get_history(self, limit=50, offset=0) -> list:
        """Get paginated conversation history, most recent first."""
        uid = current_user_id.get()
        if not uid or not self._ensure_connection():
            return []
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, timestamp, user_input, assistant_response FROM conversations "
                "WHERE user_id = %s ORDER BY id DESC LIMIT %s OFFSET %s",
                (uid, limit, offset)
            )
            rows = cur.fetchall()
        return [
            {
                "id": row[0],
                "timestamp": row[1].isoformat() if row[1] else None,
                "user_input": row[2],
                "assistant_response": row[3],
            }
            for row in rows
        ]

    def get_history_count(self) -> int:
        uid = current_user_id.get()
        if not uid or not self._ensure_connection():
            return 0
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM conversations WHERE user_id = %s", (uid,))
            return cur.fetchone()[0]

    def retrieve(self, query: str, n=3) -> list:
        """Retrieve semantically relevant past memories."""
        try:
            uid = current_user_id.get()
            if not uid or not self._ensure_connection():
                return []
            embedding = self._embed(query)
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT user_input, assistant_response FROM conversations "
                    "WHERE user_id = %s ORDER BY embedding <=> %s LIMIT %s",
                    (uid, embedding, n)
                )
                rows = cur.fetchall()
            if not rows:
                return []

            memory_text = "\n---\n".join(f"User: {u}\nJOESTAR: {a}" for u, a in rows)
            return [{
                "role": "user",
                "content": f"[RELEVANT MEMORY]\n{memory_text}\n[END MEMORY]"
            }, {
                "role": "assistant",
                "content": "Understood. I have that context loaded."
            }]
        except Exception:
            return []
