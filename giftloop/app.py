from datetime import datetime, timezone
from pathlib import Path
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

BASE = Path(__file__).parent
DB = BASE / "giftloop.db"
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_CURRENCY = os.getenv("STRIPE_PRICE_CURRENCY", "eur").lower()
PLATFORM_FEE_PERCENT = float(os.getenv("PLATFORM_FEE_PERCENT", "5"))

app = FastAPI(title="GiftLoop", docs_url=None, redoc_url=None)

SCHEMA = """
CREATE TABLE IF NOT EXISTS gifts (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  recipient TEXT NOT NULL,
  target REAL NOT NULL,
  currency TEXT NOT NULL DEFAULT 'EUR',
  message TEXT DEFAULT '',
  deadline TEXT,
  owner_token_hash TEXT NOT NULL,
  stripe_account_id TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contributions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  gift_id TEXT NOT NULL,
  name TEXT NOT NULL,
  amount REAL NOT NULL,
  note TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pledged',
  stripe_session_id TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(gift_id) REFERENCES gifts(id)
);
CREATE INDEX IF NOT EXISTS idx_contributions_gift_id ON contributions(gift_id);
CREATE INDEX IF NOT EXISTS idx_contributions_session_id ON contributions(stripe_session_id);
"""

RATE_LIMIT = defaultdict(deque)
RATE_WINDOW_SECONDS = 60
RATE_MAX_REQUESTS = 30


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def check_owner(gift_row: sqlite3.Row, token: str | None):
    if not token or not hmac.compare_digest(gift_row["owner_token_hash"], token_hash(token)):
        raise HTTPException(403, "Owner access required")


def parse_deadline(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError as exc:
        raise HTTPException(422, "deadline must be a valid ISO-8601 timestamp") from exc


def gift_status(gift: sqlite3.Row, total: float) -> str:
    if total >= gift["target"]:
        return "funded"
    deadline = parse_deadline(gift["deadline"])
    if deadline and deadline <= datetime.now(timezone.utc):
        return "closed"
    return "open"


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    client_host = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = RATE_LIMIT[client_host]
    while bucket and now - bucket[0] > RATE_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= RATE_MAX_REQUESTS:
        return JSONResponse({"detail": "Too many requests"}, status_code=429,
                            headers={"Retry-After": str(RATE_WINDOW_SECONDS)})
    bucket.append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


class GiftCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    recipient: str = Field(min_length=1, max_length=80)
    target: float = Field(gt=0, le=1_000_000)
    currency: str = Field(default="EUR", min_length=1, max_length=8)
    message: str = Field(default="", max_length=500)
    deadline: str | None = None


class ContributionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    amount: float = Field(gt=0, le=100_000)
    note: str = Field(default="", max_length=240)


class OwnerAction(BaseModel):
    owner_token: str = Field(min_length=16, max_length=200)


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE / "index.html").read_text(encoding="utf-8")


@app.get("/g/{gift_id}", response_class=HTMLResponse)
def gift_page(gift_id: str):
    return (BASE / "index.html").read_text(encoding="utf-8")


@app.post("/api/gifts")
def create_gift(payload: GiftCreate):
    parse_deadline(payload.deadline)
    gift_id = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12]
    owner_token = secrets.token_urlsafe(32)
    conn = db()
    conn.execute(
        "INSERT INTO gifts(id,title,recipient,target,currency,message,deadline,owner_token_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            gift_id,
            payload.title.strip(),
            payload.recipient.strip(),
            payload.target,
            payload.currency.upper().strip(),
            payload.message.strip(),
            payload.deadline,
            token_hash(owner_token),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {
        "id": gift_id,
        "url": f"/g/{gift_id}",
        "owner_token": owner_token,
        "owner_url": f"/manage/{gift_id}?token={owner_token}",
    }


@app.get("/api/gifts/{gift_id}")
def get_gift(gift_id: str):
    conn = db()
    gift = conn.execute("SELECT * FROM gifts WHERE id=?", (gift_id,)).fetchone()
    if not gift:
        conn.close()
        raise HTTPException(404, "Gift not found")
    rows = conn.execute(
        "SELECT name,amount,note,status,created_at FROM contributions WHERE gift_id=? AND status!='cancelled' ORDER BY id DESC",
        (gift_id,),
    ).fetchall()
    total = round(sum(r["amount"] for r in rows if r["status"] in {"pledged", "paid"}), 2)
    status = gift_status(gift, total)
    conn.close()
    remaining = round(max(0, gift["target"] - total), 2)
    return {
        "gift": {k: gift[k] for k in gift.keys() if k != "owner_token_hash"},
        "contributions": [dict(r) for r in rows],
        "total": total,
        "remaining": remaining,
        "status": status,
    }


@app.post("/api/gifts/{gift_id}/contributions")
def contribute(gift_id: str, payload: ContributionCreate):
    conn = db()
    gift = conn.execute("SELECT * FROM gifts WHERE id=?", (gift_id,)).fetchone()
    if not gift:
        conn.close()
        raise HTTPException(404, "Gift not found")
    rows = conn.execute("SELECT amount,status FROM contributions WHERE gift_id=?", (gift_id,)).fetchall()
    total = sum(r["amount"] for r in rows if r["status"] in {"pledged", "paid"})
    if gift_status(gift, total) != "open":
        conn.close()
        raise HTTPException(409, "This gift is closed")
    conn.execute(
        "INSERT INTO contributions(gift_id,name,amount,note,status,created_at) VALUES(?,?,?,?,?,?)",
        (gift_id, payload.name.strip(), payload.amount, payload.note.strip(), "pledged", datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "status": "pledged"}


@app.post("/api/gifts/{gift_id}/connect/stripe")
def save_stripe_account(gift_id: str, payload: OwnerAction):
    conn = db()
    gift = conn.execute("SELECT * FROM gifts WHERE id=?", (gift_id,)).fetchone()
    if not gift:
        conn.close()
        raise HTTPException(404, "Gift not found")
    check_owner(gift, payload.owner_token)
    conn.close()
    raise HTTPException(501, "Stripe Connect onboarding must be completed after the platform Stripe account is connected")


@app.post("/api/gifts/{gift_id}/checkout")
def create_checkout(gift_id: str, payload: ContributionCreate):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Payments are not configured")
    raise HTTPException(501, "Stripe Checkout is scaffolded but requires a connected organizer account and production webhook configuration")


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("stripe-signature", "")
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "Stripe webhook is not configured")
    # Signature verification placeholder. Production deployment must use Stripe's official library.
    if not signature:
        raise HTTPException(400, "Missing Stripe signature")
    return {"received": True}
