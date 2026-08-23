import sqlite3
import chromadb
from datetime import datetime
from pathlib import Path

# Ensure data directory exists
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

class Memory:
    def __init__(self):
        # Short-term: SQLite
        self.conn = sqlite3.connect(str(DATA_DIR / "joestar.db"), check_same_thread=False)
        self._init_db()

        # Long-term: ChromaDB vector store
        self.chroma = chromadb.PersistentClient(path=str(DATA_DIR / "chroma"))
        self.collection = self.chroma.get_or_create_collection("joestar_memory")

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                user_input TEXT,
                assistant_response TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self.conn.commit()

    def get_last_reflection_time(self):
        cur = self.conn.execute("SELECT value FROM app_state WHERE key = 'last_reflection_at'")
        row = cur.fetchone()
        return row[0] if row else None

    def set_last_reflection_time(self, iso_timestamp: str):
        self.conn.execute(
            "INSERT INTO app_state (key, value) VALUES ('last_reflection_at', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (iso_timestamp,)
        )
        self.conn.commit()

    def save(self, user_input: str, response: str):
        # Save to SQLite
        self.conn.execute(
            "INSERT INTO conversations VALUES (NULL, ?, ?, ?)",
            (datetime.now().isoformat(), user_input, response)
        )
        self.conn.commit()

        # Save to ChromaDB for semantic search
        self.collection.add(
            documents=[f"User: {user_input}\nJOESTAR: {response}"],
            ids=[f"mem_{datetime.now().timestamp()}"]
        )

    def get_recent(self, n=5) -> list:
        """Get the n most recent exchanges, oldest first."""
        cur = self.conn.execute(
            "SELECT user_input, assistant_response FROM conversations ORDER BY id DESC LIMIT ?",
            (n,)
        )
        return list(reversed(cur.fetchall()))

    def get_history(self, limit=50, offset=0) -> list:
        """Get paginated conversation history, most recent first."""
        cur = self.conn.execute(
            "SELECT id, timestamp, user_input, assistant_response FROM conversations ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return [
            {"id": row[0], "timestamp": row[1], "user_input": row[2], "assistant_response": row[3]}
            for row in cur.fetchall()
        ]

    def get_history_count(self) -> int:
        cur = self.conn.execute("SELECT COUNT(*) FROM conversations")
        return cur.fetchone()[0]

    def retrieve(self, query: str, n=3) -> list:
        """Retrieve semantically relevant past memories."""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n
            )
            docs = results["documents"][0]
            if not docs:
                return []

            memory_text = "\n---\n".join(docs)
            return [{
                "role": "user",
                "content": f"[RELEVANT MEMORY]\n{memory_text}\n[END MEMORY]"
            }, {
                "role": "assistant",
                "content": "Understood. I have that context loaded."
            }]
        except Exception:
            return []