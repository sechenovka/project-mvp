# GiftLoop MVP

A tiny viral-first group-gift MVP.

## Core loop

1. Organizer creates a gift page.
2. Service produces one shareable link.
3. Organizer drops it into a group chat.
4. Friends contribute without an account or app.
5. Every contributor is a potential organizer for the next gift.

## Run

```bash
python -m venv .venv
.venv\\Scripts\\activate  # Windows
pip install -r requirements.txt
uvicorn app:app --reload
```

Open http://127.0.0.1:8000
