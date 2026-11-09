import json
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np


class MemoryStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                field_type TEXT NOT NULL,
                options TEXT NOT NULL,
                domain TEXT NOT NULL,
                selector_hint TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    @staticmethod
    def _encode(vector: list[float]) -> bytes:
        return np.asarray(vector, dtype=np.float32).tobytes()

    @staticmethod
    def _decode(blob: bytes) -> np.ndarray:
        return np.frombuffer(blob, dtype=np.float32)

    def count(self) -> int:
        with self._connect() as db:
            return int(db.execute("SELECT COUNT(*) FROM memories").fetchone()[0])

    def add(self, question: str, answer: str, field_type: str, options: list[str], domain: str, selector_hint: str, embedding: list[float]) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO memories(question, answer, field_type, options, domain, selector_hint, embedding) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (question, answer, field_type, json.dumps(options), domain, selector_hint, self._encode(embedding)),
            )

    def find_similar(self, embedding: list[float], threshold: float = 0.86) -> dict[str, Any] | None:
        query = np.asarray(embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return None
        best: tuple[float, dict[str, Any] | None] = (-1.0, None)
        with self._connect() as db:
            rows = db.execute("SELECT question, answer, field_type, options, domain, selector_hint, embedding FROM memories").fetchall()
        for question, answer, field_type, options, domain, selector_hint, blob in rows:
            stored = self._decode(blob)
            denominator = query_norm * np.linalg.norm(stored)
            score = float(np.dot(query, stored) / denominator) if denominator else 0.0
            if score > best[0]:
                best = (score, {"question": question, "answer": answer, "field_type": field_type, "options": json.loads(options), "domain": domain, "selector_hint": selector_hint, "confidence": score})
        return best[1] if best[1] and best[0] >= threshold else None
