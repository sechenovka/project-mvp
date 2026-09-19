from datetime import datetime, timezone
from pathlib import Path
import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

BASE = Path(__file__).parent
DB = BASE / "giftloop.db"
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
CLOUDPAYMENTS_PUBLIC_ID = os.getenv("CLOUDPAYMENTS_PUBLIC_ID", "")
CLOUDPAYMENTS_API_SECRET = os.getenv("CLOUDPAYMENTS_API_SECRET", "")
GIFTLOOP_PREMIUM_PRICE_RUB = int(os.getenv("GIFTLOOP_PREMIUM_PRICE_RUB", "199"))

app = FastAPI(title="GiftLoop", version="0.3.0", docs_url=None, redoc_url=None)

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
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contributions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  gift_id TEXT NOT NULL,
  name TEXT NOT NULL,
  amount REAL NOT NULL,
  note TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pledged',
  created_at TEXT NOT NULL,
  FOREIGN KEY(gift_id) REFERENCES gifts(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_contributions_gift_id ON contributions(gift_id);
CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_id TEXT NOT NULL UNIQUE,
  transaction_id TEXT UNIQUE,
  product TEXT NOT NULL,
  amount REAL NOT NULL,
  currency TEXT NOT NULL DEFAULT 'RUB',
  status TEXT NOT NULL DEFAULT 'pending',
  raw_payload TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
"""

RATE_LIMIT = defaultdict(deque)
RATE_WINDOW_SECONDS = 60
RATE_MAX_REQUESTS = 30

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

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
        return JSONResponse({"detail": "Too many requests"}, status_code=429, headers={"Retry-After": str(RATE_WINDOW_SECONDS)})
    bucket.append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://widget.cloudpayments.ru; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https://*.cloudpayments.ru; "
        "connect-src 'self' https://*.cloudpayments.ru; "
        "frame-src https://widget.cloudpayments.ru https://*.cloudpayments.ru; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
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

@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE / "index.html").read_text(encoding="utf-8")

@app.get("/g/{gift_id}", response_class=HTMLResponse)
def gift_page(gift_id: str):
    return (BASE / "index.html").read_text(encoding="utf-8")

@app.get("/api/config")
def config():
    return {
        "payments_enabled": bool(CLOUDPAYMENTS_PUBLIC_ID),
        "cloudpayments_public_id": CLOUDPAYMENTS_PUBLIC_ID,
        "premium_price_rub": GIFTLOOP_PREMIUM_PRICE_RUB,
        "currency": "RUB",
    }

@app.post("/api/gifts")
def create_gift(payload: GiftCreate):
    parse_deadline(payload.deadline)
    gift_id = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12]
    owner_token = secrets.token_urlsafe(32)
    conn = db()
    try:
        conn.execute(
            "INSERT INTO gifts(id,title,recipient,target,currency,message,deadline,owner_token_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                gift_id,
                payload.title.strip(),
                payload.recipient.strip(),
                round(payload.target, 2),
                payload.currency.strip().upper(),
                payload.message.strip(),
                payload.deadline,
                token_hash(owner_token),
                now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": gift_id, "url": f"/g/{gift_id}", "owner_token": owner_token}

@app.get("/api/gifts/{gift_id}")
def get_gift(gift_id: str):
    conn = db()
    try:
        gift = conn.execute("SELECT * FROM gifts WHERE id=?", (gift_id,)).fetchone()
        if not gift:
            raise HTTPException(404, "Gift not found")
        rows = conn.execute(
            "SELECT name,amount,note,status,created_at FROM contributions WHERE gift_id=? AND status!='cancelled' ORDER BY id DESC",
            (gift_id,),
        ).fetchall()
        total = round(sum(float(r["amount"]) for r in rows if r["status"] in {"pledged", "paid"}), 2)
        remaining = round(max(0, gift["target"] - total), 2)
        return {
            "gift": {k: gift[k] for k in gift.keys() if k != "owner_token_hash"},
            "contributions": [dict(r) for r in rows],
            "total": total,
            "remaining": remaining,
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
        rows = conn.execute("SELECT amount,status FROM contributions WHERE gift_id=?", (gift_id,)).fetchall()
        total = sum(r["amount"] for r in rows if r["status"] in {"pledged", "paid"})
        if gift_status(gift, total) != "open":
            raise HTTPException(409, "This gift is closed")
        conn.execute(
            "INSERT INTO contributions(gift_id,name,amount,note,status,created_at) VALUES(?,?,?,?,?,?)",
            (gift_id, payload.name.strip(), round(payload.amount, 2), payload.note.strip(), "pledged", now_iso()),
        )
        conn.commit()
        return {"ok": True, "status": "pledged"}
    finally:
        conn.close()

def verify_cloudpayments_hmac(body: bytes, signature: str) -> bool:
    if not CLOUDPAYMENTS_API_SECRET or not signature:
        return False
    digest = hmac.new(CLOUDPAYMENTS_API_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, signature)

@app.post("/api/payments/intents")
def create_payment_intent():
    if not CLOUDPAYMENTS_PUBLIC_ID:
        raise HTTPException(503, "Payments are not configured")
    invoice_id = f"GL-{secrets.token_hex(8).upper()}"
    amount = float(GIFTLOOP_PREMIUM_PRICE_RUB)
    now = now_iso()
    conn = db()
    try:
        conn.execute(
            "INSERT INTO payments(invoice_id,product,amount,currency,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (invoice_id, "GiftLoop Plus", amount, "RUB", "pending", now, now),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "invoice_id": invoice_id,
        "amount": amount,
        "currency": "RUB",
        "public_id": CLOUDPAYMENTS_PUBLIC_ID,
        "description": "GiftLoop Plus",
    }

@app.get("/api/payments/{invoice_id}")
def payment_status(invoice_id: str):
    conn = db()
    try:
        row = conn.execute(
            "SELECT invoice_id,product,amount,currency,status,transaction_id FROM payments WHERE invoice_id=?",
            (invoice_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Payment not found")
        return dict(row)
    finally:
        conn.close()

@app.post("/webhooks/cloudpayments/pay")
async def cloudpayments_pay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Content-HMAC", "")
    if not verify_cloudpayments_hmac(body, signature):
        raise HTTPException(403, "Invalid webhook signature")
    raw = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    payload = {key: values[-1] for key, values in raw.items()}
    if not payload:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(400, "Invalid webhook payload") from exc
    invoice_id = str(payload.get("InvoiceId", "")).strip()
    transaction_id = str(payload.get("TransactionId", "")).strip()
    if not invoice_id or not transaction_id:
        raise HTTPException(400, "InvoiceId and TransactionId are required")
    conn = db()
    try:
        payment = conn.execute("SELECT * FROM payments WHERE invoice_id=?", (invoice_id,)).fetchone()
        if not payment:
            raise HTTPException(404, "Unknown invoice")
        amount = float(payload.get("Amount", payment["amount"]))
        currency = str(payload.get("Currency", payment["currency"])).upper()
        if round(amount, 2) != round(float(payment["amount"]), 2) or currency != payment["currency"]:
            raise HTTPException(400, "Payment amount or currency mismatch")
        now = now_iso()
        conn.execute(
            "UPDATE payments SET transaction_id=?,status='paid',raw_payload=?,updated_at=? WHERE invoice_id=?",
            (transaction_id, body.decode("utf-8", errors="replace"), now, invoice_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"code": 0}
