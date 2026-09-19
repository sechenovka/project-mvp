import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import app


def test_flow(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(app, "DB", tmp_path / "test.db")
    client = TestClient(app.app)

    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    created = client.post(
        "/api/gifts",
        json={"title": "Headphones", "recipient": "Alex", "target": 100, "currency": "EUR", "deadline": future},
    )
    assert created.status_code == 200
    gift_id = created.json()["id"]
    assert created.json()["owner_token"]

    page = client.get(f"/g/{gift_id}")
    assert page.status_code == 200
    assert "GiftLoop" in page.text

    state = client.get(f"/api/gifts/{gift_id}")
    assert state.status_code == 200
    assert state.json()["total"] == 0
    assert state.json()["remaining"] == 100
    assert state.json()["status"] == "open"
    assert "owner_token_hash" not in state.json()["gift"]

    added = client.post(
        f"/api/gifts/{gift_id}/contributions",
        json={"name": "Jamie", "amount": 25, "note": "Happy birthday"},
    )
    assert added.status_code == 200

    state = client.get(f"/api/gifts/{gift_id}").json()
    assert state["total"] == 25
    assert state["remaining"] == 75
    assert len(state["contributions"]) == 1


def test_closed_gift_rejects_contribution(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(app, "DB", tmp_path / "closed.db")
    client = TestClient(app.app)
    created = client.post(
        "/api/gifts",
        json={"title": "Gift", "recipient": "Sam", "target": 20, "deadline": (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()},
    )
    assert created.status_code == 200
    gift_id = created.json()["id"]
    conn = app.db()
    conn.execute("UPDATE gifts SET deadline=? WHERE id=?", ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), gift_id))
    conn.commit()
    conn.close()
    response = client.post(f"/api/gifts/{gift_id}/contributions", json={"name": "Sam", "amount": 5})
    assert response.status_code == 409


def test_payment_intent_and_webhook(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(app, "DB", tmp_path / "payments.db")
    monkeypatch.setattr(app, "CLOUDPAYMENTS_PUBLIC_ID", "pk_test_demo")
    monkeypatch.setattr(app, "CLOUDPAYMENTS_API_SECRET", "secret-demo")
    client = TestClient(app.app)

    intent = client.post("/api/payments/intents")
    assert intent.status_code == 200
    payload = intent.json()
    assert payload["currency"] == "RUB"

    body = f"TransactionId=123456&Amount={payload['amount']:.2f}&Currency=RUB&InvoiceId={payload['invoice_id']}".encode()
    signature = base64.b64encode(hmac.new(b"secret-demo", body, hashlib.sha256).digest()).decode()
    webhook = client.post(
        "/webhooks/cloudpayments/pay",
        content=body,
        headers={"Content-HMAC": signature, "Content-Type": "application/x-www-form-urlencoded"},
    )
    assert webhook.status_code == 200
    assert webhook.json() == {"code": 0}

    status = client.get(f"/api/payments/{payload['invoice_id']}")
    assert status.json()["status"] == "paid"
    assert status.json()["transaction_id"] == "123456"


def test_invalid_webhook_signature_rejected(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(app, "DB", tmp_path / "bad-webhook.db")
    monkeypatch.setattr(app, "CLOUDPAYMENTS_PUBLIC_ID", "pk_test_demo")
    monkeypatch.setattr(app, "CLOUDPAYMENTS_API_SECRET", "secret-demo")
    client = TestClient(app.app)

    intent = client.post("/api/payments/intents").json()
    body = f"TransactionId=123456&Amount={intent['amount']:.2f}&Currency=RUB&InvoiceId={intent['invoice_id']}".encode()
    webhook = client.post("/webhooks/cloudpayments/pay", content=body, headers={"Content-HMAC": "bad"})
    assert webhook.status_code == 403


def test_security_headers(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(app, "DB", tmp_path / "headers.db")
    client = TestClient(app.app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "Content-Security-Policy" in response.headers
