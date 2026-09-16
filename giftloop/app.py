from datetime import datetime, timezone
from pathlib import Path
import secrets
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

BASE = Path(__file__).parent
DB = BASE / "giftloop.db"
app = FastAPI(title="GiftLoop", version="0.2.0")

SCHEMA = """
CREATE TABLE IF NOT EXISTS gifts (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  recipient TEXT NOT NULL,
  target REAL NOT NULL,
  currency TEXT NOT NULL DEFAULT 'EUR',
  message TEXT DEFAULT '',
  deadline TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contributions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  gift_id TEXT NOT NULL,
  name TEXT NOT NULL,
  amount REAL NOT NULL,
  note TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  FOREIGN KEY(gift_id) REFERENCES gifts(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_contributions_gift_id ON contributions(gift_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    return conn


class GiftCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    recipient: str = Field(min_length=1, max_length=80)
    target: float = Field(gt=0, le=1_000_000)
    currency: str = Field(default="EUR", min_length=1, max_length=8)
    message: str = Field(default="", max_length=500)
    deadline: datetime | None = None

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if not value.isalnum():
            raise ValueError("Currency must contain letters or digits only")
        return value

    @field_validator("deadline")
    @classmethod
    def future_deadline(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            if value <= datetime.now(timezone.utc):
                raise ValueError("Deadline must be in the future")
        return value


class ContributionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    amount: float = Field(gt=0, le=100_000)
    note: str = Field(default="", max_length=240)


def gift_status(gift: sqlite3.Row, total: float) -> str:
    if gift["deadline"]:
        deadline = datetime.fromisoformat(gift["deadline"])
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if deadline <= datetime.now(timezone.utc):
            return "closed"
    if total >= gift["target"]:
        return "funded"
    return "open"


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (BASE / "index.html").read_text(encoding="utf-8")


@app.get("/g/{gift_id}", response_class=HTMLResponse)
def gift_page(gift_id: str) -> str:
    return (BASE / "index.html").read_text(encoding="utf-8")


@app.post("/api/gifts")
def create_gift(payload: GiftCreate):
    gift_id = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12]
    deadline = payload.deadline.isoformat() if payload.deadline else None
    conn = db()
    try:
        conn.execute(
            "INSERT INTO gifts(id,title,recipient,target,currency,message,deadline,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                gift_id,
                payload.title.strip(),
                payload.recipient.strip(),
                round(payload.target, 2),
                payload.currency.strip().upper(),
                payload.message.strip(),
                deadline,
                now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": gift_id, "url": f"/g/{gift_id}"}


@app.get("/api/gifts/{gift_id}")
def get_gift(gift_id: str):
    conn = db()
    try:
        gift = conn.execute("SELECT * FROM gifts WHERE id=?", (gift_id,)).fetchone()
        if not gift:
            raise HTTPException(404, "Gift not found")
        rows = conn.execute(
            "SELECT name,amount,note,created_at FROM contributions WHERE gift_id=? ORDER BY id DESC",
            (gift_id,),
        ).fetchall()
        total = round(sum(float(row["amount"]) for row in rows), 2)
        return {
            "gift": dict(gift),
            "contributions": [dict(row) for row in rows],
            "total": total,
            "remaining": round(max(gift["target"] - total, 0), 2),
            "status": gift_status(gift, total),
        }
    finally:
        conn.close()


@app.post("/api/gifts/{gift_id}/contributions")
def contribute(gift_id: str, payload: ContributionCreate):
    conn = db()
    try:
        gift = conn.execute("SELECT * FROM gifts WHERE id=?", (gift_id,)).fetchone()
        if not gift:
            raise HTTPException(404, "Gift not found")
        rows = conn.execute("SELECT amount FROM contributions WHERE gift_id=?", (gift_id,)).fetchall()
        total = round(sum(float(row["amount"]) for row in rows), 2)
        status = gift_status(gift, total)
        if status == "closed":
            raise HTTPException(409, "This gift is closed")
        amount = round(payload.amount, 2)
        conn.execute(
            "INSERT INTO contributions(gift_id,name,amount,note,created_at) VALUES(?,?,?,?,?)",
            (gift_id, payload.name.strip(), amount, payload.note.strip(), now_iso()),
        )
        conn.commit()
        return {"ok": True, "status": gift_status(gift, total + amount)}
    finally:
        conn.close()
