# GiftLoop

GiftLoop is a viral-first group-gift MVP: create one gift link, drop it into a group chat, and let everyone contribute without an account or app.

## Core loop

1. Organizer creates a gift page.
2. GiftLoop generates a shareable URL.
3. Organizer shares it in WhatsApp, Telegram, Discord, email, or SMS.
4. Friends contribute from the browser without signing up.
5. Contributors can become organizers for the next gift.

## MVP features

- One-link group gift pages
- Contributions without accounts
- Live funding progress
- Optional collection deadline
- Open / funded / closed states
- Share button with Web Share API fallback
- SQLite persistence
- FastAPI backend
- Basic input validation and tests

## Run locally

```bash
python -m venv .venv
.venv\\Scripts\\activate  # Windows
pip install -r requirements.txt
uvicorn app:app --reload
```

Open http://127.0.0.1:8000

Run tests:

```bash
pytest -q
```

## Product direction

The MVP deliberately does not process real money yet. The first goal is to validate the viral loop and repeat usage around group gifts. Payment collection should be added only after validating demand and selecting the appropriate regulated payment flow.
