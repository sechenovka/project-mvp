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

    page = client.get(f"/g/{gift_id}")
    assert page.status_code == 200
    assert "GiftLoop" in page.text

    state = client.get(f"/api/gifts/{gift_id}")
    assert state.status_code == 200
    assert state.json()["total"] == 0
    assert state.json()["remaining"] == 100
    assert state.json()["status"] == "open"

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
    gift_id = created.json()["id"]
    conn = app.db()
    conn.execute("UPDATE gifts SET deadline=? WHERE id=?", ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), gift_id))
    conn.commit(); conn.close()
    response = client.post(f"/api/gifts/{gift_id}/contributions", json={"name":"Sam","amount":5})
    assert response.status_code == 409
