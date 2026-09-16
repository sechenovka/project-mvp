from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pathlib import Path
import secrets
import sqlite3
from datetime import datetime, timezone

BASE = Path(__file__).parent
DB = BASE / 'giftloop.db'
app = FastAPI(title='GiftLoop MVP')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS gifts (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  recipient TEXT NOT NULL,
  target REAL NOT NULL,
  currency TEXT NOT NULL DEFAULT 'EUR',
  message TEXT DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contributions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  gift_id TEXT NOT NULL,
  name TEXT NOT NULL,
  amount REAL NOT NULL,
  note TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  FOREIGN KEY(gift_id) REFERENCES gifts(id)
);
'''

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn

class GiftCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    recipient: str = Field(min_length=1, max_length=80)
    target: float = Field(gt=0, le=1_000_000)
    currency: str = Field(default='EUR', min_length=1, max_length=8)
    message: str = Field(default='', max_length=500)

class ContributionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    amount: float = Field(gt=0, le=100_000)
    note: str = Field(default='', max_length=240)

@app.get('/', response_class=HTMLResponse)
def index():
    return (BASE / 'index.html').read_text(encoding='utf-8')

@app.get('/g/{gift_id}', response_class=HTMLResponse)
def gift_page(gift_id: str):
    return (BASE / 'index.html').read_text(encoding='utf-8')

@app.post('/api/gifts')
def create_gift(payload: GiftCreate):
    gift_id = secrets.token_urlsafe(7).replace('-', '').replace('_', '')[:10]
    conn = db()
    conn.execute(
        'INSERT INTO gifts(id,title,recipient,target,currency,message,created_at) VALUES(?,?,?,?,?,?,?)',
        (gift_id, payload.title.strip(), payload.recipient.strip(), payload.target, payload.currency.upper().strip(), payload.message.strip(), datetime.now(timezone.utc).isoformat())
    )
    conn.commit(); conn.close()
    return {'id': gift_id, 'url': f'/g/{gift_id}'}

@app.get('/api/gifts/{gift_id}')
def get_gift(gift_id: str):
    conn = db()
    gift = conn.execute('SELECT * FROM gifts WHERE id=?', (gift_id,)).fetchone()
    if not gift:
        conn.close(); raise HTTPException(404, 'Gift not found')
    rows = conn.execute('SELECT name,amount,note,created_at FROM contributions WHERE gift_id=? ORDER BY id DESC', (gift_id,)).fetchall()
    total = sum(r['amount'] for r in rows)
    conn.close()
    return {'gift': dict(gift), 'contributions': [dict(r) for r in rows], 'total': round(total,2)}

@app.post('/api/gifts/{gift_id}/contributions')
def contribute(gift_id: str, payload: ContributionCreate):
    conn = db()
    if not conn.execute('SELECT 1 FROM gifts WHERE id=?', (gift_id,)).fetchone():
        conn.close(); raise HTTPException(404, 'Gift not found')
    conn.execute('INSERT INTO contributions(gift_id,name,amount,note,created_at) VALUES(?,?,?,?,?)',
                 (gift_id,payload.name.strip(),payload.amount,payload.note.strip(),datetime.now(timezone.utc).isoformat()))
    conn.commit(); conn.close()
    return {'ok': True}
