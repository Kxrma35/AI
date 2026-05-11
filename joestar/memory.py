import sqlite3
import chromadb
from datetime import datetime

class Memory:
    def __init__(self):
        # Short-term: SQLite
        self.conn = sqlite3.connect("data/joestar.db", check_same_thread=False)
        self._init_db()

        # Long-term: ChromaDB vector store
        self.chroma = chromadb.PersistentClient(path="data/chroma")
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

    def retrieve(self, query: str, n=5) -> list:
        """Retrieve semantically relevant past memories."""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n
            )
            docs = results["documents"][0]
            if not docs:
                return []

            # Format as context message
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