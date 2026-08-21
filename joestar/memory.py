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