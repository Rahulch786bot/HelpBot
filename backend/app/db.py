"""
Ticket store.

Uses a small SQLite database seeded from the provided tickets.json so
that the Ticket Agent's create/status/escalate/cancel actions are real
persisted state changes (real backend endpoints / real tool calls), not
just re-reads of a static file. SQLite was chosen over standing up
Postgres because it needs zero infrastructure and is fully AWS
Free-Tier compatible (it's just a file next to the app on the EC2
instance / in the container).
"""
import json
import sqlite3
from datetime import datetime, timezone

from app.config import TICKETS_DB, TICKETS_JSON

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    category TEXT,
    subject TEXT,
    description TEXT,
    status TEXT,
    priority TEXT,
    created_date TEXT,
    resolution TEXT
);
"""


def get_conn():
    conn = sqlite3.connect(TICKETS_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(reset: bool = False):
    conn = get_conn()
    cur = conn.cursor()
    if reset:
        cur.execute("DROP TABLE IF EXISTS tickets")
    cur.execute(_SCHEMA)
    cur.execute("SELECT COUNT(*) AS n FROM tickets")
    if cur.fetchone()["n"] == 0:
        with open(TICKETS_JSON, encoding="utf-8") as f:
            seed = json.load(f)
        cur.executemany(
            """INSERT INTO tickets
               (ticket_id, category, subject, description, status, priority, created_date, resolution)
               VALUES (:ticket_id, :category, :subject, :description, :status, :priority, :created_date, :resolution)""",
            seed,
        )
    conn.commit()
    conn.close()


def get_ticket(ticket_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id.upper().strip(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_resolved_tickets() -> list[dict]:
    """Used by the RAG agent -- resolved tickets are a second knowledge source."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tickets WHERE status = 'Resolved'"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def next_ticket_id() -> str:
    conn = get_conn()
    row = conn.execute(
        "SELECT ticket_id FROM tickets ORDER BY ticket_id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return "TCK-1001"
    n = int(row["ticket_id"].split("-")[1]) + 1
    return f"TCK-{n}"


def create_ticket(category: str, subject: str, description: str, priority: str = "Medium") -> dict:
    ticket_id = next_ticket_id()
    conn = get_conn()
    conn.execute(
        """INSERT INTO tickets (ticket_id, category, subject, description, status, priority, created_date, resolution)
           VALUES (?, ?, ?, ?, 'Open', ?, ?, NULL)""",
        (ticket_id, category, subject, description, priority,
         datetime.now(timezone.utc).strftime("%Y-%m-%d")),
    )
    conn.commit()
    conn.close()
    return get_ticket(ticket_id)


def update_ticket_status(ticket_id: str, new_status: str) -> dict | None:
    ticket = get_ticket(ticket_id)
    if not ticket:
        return None
    conn = get_conn()
    conn.execute(
        "UPDATE tickets SET status = ? WHERE ticket_id = ?",
        (new_status, ticket_id.upper().strip()),
    )
    conn.commit()
    conn.close()
    return get_ticket(ticket_id)
