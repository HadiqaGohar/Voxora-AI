import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get("VOXORA_DB", "/data/voxora.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            type TEXT NOT NULL,
            input_text TEXT,
            output_text TEXT,
            language TEXT,
            voice TEXT,
            latency_ms REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interaction_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (interaction_id) REFERENCES interactions(id)
        );

        CREATE INDEX IF NOT EXISTS idx_interactions_session ON interactions(session_id);
        CREATE INDEX IF NOT EXISTS idx_interactions_type ON interactions(type);
        CREATE INDEX IF NOT EXISTS idx_interactions_created ON interactions(created_at);
        CREATE INDEX IF NOT EXISTS idx_feedback_interaction ON feedback(interaction_id);
    """)
    conn.close()


def log_interaction(session_id: str, type: str, input_text: str = None,
                    output_text: str = None, language: str = None,
                    voice: str = None, latency_ms: float = None) -> int:
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO interactions (session_id, type, input_text, output_text, language, voice, latency_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_id, type, input_text, output_text, language, voice, latency_ms)
    )
    interaction_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return interaction_id


def add_feedback(interaction_id: int, rating: int, comment: str = None):
    conn = get_db()
    conn.execute(
        "INSERT INTO feedback (interaction_id, rating, comment) VALUES (?, ?, ?)",
        (interaction_id, rating, comment)
    )
    conn.commit()
    conn.close()


def get_analytics():
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) as c FROM interactions").fetchone()["c"]

    by_type = conn.execute(
        "SELECT type, COUNT(*) as count, AVG(latency_ms) as avg_latency FROM interactions GROUP BY type"
    ).fetchall()

    by_language = conn.execute(
        "SELECT language, COUNT(*) as count FROM interactions WHERE language IS NOT NULL GROUP BY language ORDER BY count DESC LIMIT 20"
    ).fetchall()

    by_day = conn.execute(
        "SELECT DATE(created_at) as day, COUNT(*) as count FROM interactions GROUP BY day ORDER BY day DESC LIMIT 30"
    ).fetchall()

    feedback_stats = conn.execute(
        "SELECT rating, COUNT(*) as count FROM feedback GROUP BY rating ORDER BY rating"
    ).fetchall()

    avg_feedback = conn.execute(
        "SELECT AVG(rating) as avg_rating FROM feedback"
    ).fetchone()["avg_rating"]

    recent = conn.execute(
        "SELECT i.id, i.type, i.input_text, i.language, i.latency_ms, i.created_at, f.rating FROM interactions i LEFT JOIN feedback f ON f.interaction_id = i.id ORDER BY i.created_at DESC LIMIT 50"
    ).fetchall()

    conn.close()

    return {
        "total_interactions": total,
        "by_type": [dict(r) for r in by_type],
        "by_language": [dict(r) for r in by_language],
        "by_day": [dict(r) for r in by_day],
        "feedback_stats": [dict(r) for r in feedback_stats],
        "avg_feedback": round(avg_feedback, 2) if avg_feedback else None,
        "recent_interactions": [dict(r) for r in recent],
    }
