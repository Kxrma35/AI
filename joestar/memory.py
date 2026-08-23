import os
from datetime import datetime

import psycopg2
from pgvector.psycopg2 import register_vector
from chromadb.utils import embedding_functions

EMBEDDING_DIM = 384


class Memory:
    def __init__(self):
        self.conn_string = os.getenv("SUPABASE_DB_URL")
        self._embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        self._connect()
        self._init_db()

    def _connect(self):
        self.conn = psycopg2.connect(self.conn_string, sslmode="require", connect_timeout=10)
        self.conn.autocommit = True
        register_vector(self.conn)

    def _ensure_connection(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
        except Exception:
            self._connect()

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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

    def get_last_reflection_time(self):
        self._ensure_connection()
        with self.conn.cursor() as cur:
            cur.execute("SELECT value FROM app_state WHERE key = 'last_reflection_at'")
            row = cur.fetchone()
            return row[0] if row else None

    def set_last_reflection_time(self, iso_timestamp: str):
        self._ensure_connection()
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_state (key, value) VALUES ('last_reflection_at', %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (iso_timestamp,)
            )

    def save(self, user_input: str, response: str):
        self._ensure_connection()
        embedding = self._embed(f"User: {user_input}\nJOESTAR: {response}")
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (user_input, assistant_response, embedding) VALUES (%s, %s, %s)",
                (user_input, response, embedding)
            )

    def get_recent(self, n=5) -> list:
        """Get the n most recent exchanges, oldest first."""
        self._ensure_connection()
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT user_input, assistant_response FROM conversations ORDER BY id DESC LIMIT %s",
                (n,)
            )
            rows = cur.fetchall()
        return list(reversed(rows))

    def get_history(self, limit=50, offset=0) -> list:
        """Get paginated conversation history, most recent first."""
        self._ensure_connection()
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, timestamp, user_input, assistant_response FROM conversations "
                "ORDER BY id DESC LIMIT %s OFFSET %s",
                (limit, offset)
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
        self._ensure_connection()
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM conversations")
            return cur.fetchone()[0]

    def retrieve(self, query: str, n=3) -> list:
        """Retrieve semantically relevant past memories."""
        try:
            self._ensure_connection()
            embedding = self._embed(query)
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT user_input, assistant_response FROM conversations "
                    "ORDER BY embedding <=> %s LIMIT %s",
                    (embedding, n)
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
