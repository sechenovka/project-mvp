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
- Request rate limiting
- Security headers and restrictive CSP
- Random owner secret stored only as a hash
- Automated API/security tests
- Stripe Connect-ready boundaries (no live money movement yet)

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

## Production security

This MVP is not a production payment system. It intentionally avoids storing card data or payment secrets in the repository.

Before accepting real money, deploy behind HTTPS, put secrets in the hosting provider's secret store/environment, add centralized rate limiting (for example Redis), structured security logging, CSRF protections where cookie-authenticated state changes are introduced, backup/restore procedures, monitoring, dependency scanning, and a reviewed privacy policy/terms flow.

For authenticated organizer accounts, prefer passkeys/WebAuthn or a mature identity provider, require MFA for privileged accounts, use short-lived sessions and re-authentication for sensitive actions, and rate-limit authentication/recovery endpoints. These controls follow OWASP guidance.

## Payments

The payment boundary is deliberately isolated behind environment variables:

```text
APP_BASE_URL=https://your-domain.example
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
STRIPE_PRICE_CURRENCY=eur
PLATFORM_FEE_PERCENT=5
```

Real payouts should use a marketplace/platform product such as Stripe Connect or an equivalent regulated provider. The organizer must complete the provider's onboarding/KYC before funds can be routed to them. Do not collect money into the platform bank account and manually forward it.

The current code only defines safe boundaries and returns explicit `501`/`503` responses until a real provider account and webhook configuration are connected.

## Product direction

The initial wedge is not "another generic group-gifting site". The validation hypothesis is a chat-first flow with explicit opt-in, private contribution amounts by default, deadline reminders, and a share preview optimized for messaging apps.
