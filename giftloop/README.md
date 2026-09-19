# GiftLoop

GiftLoop is a viral-first group-gift MVP: create one gift link, share it in a group chat, and let everyone contribute without an account or app.

## Payments

GiftLoop separates product revenue from the group-gift pool.

The current paid flow is a one-time GiftLoop Plus payment in RUB. It is charged to the GiftLoop merchant account configured in CloudPayments. GiftLoop never receives or stores card numbers or CVV.

CloudPayments documents a browser widget delivered through an iframe and support for card payments including MIR. It also documents Pay webhooks and HMAC validation using the API secret, SHA-256 and Base64. Available payment methods depend on the merchant configuration.

The MVP does not hold or redistribute real group-gift funds yet. A future buyer-to-recipient flow should use an approved platform / Safe Deal arrangement rather than routing customer funds through a personal card.

## Configure CloudPayments

Set these environment variables:

APP_BASE_URL=https://your-domain.example
CLOUDPAYMENTS_PUBLIC_ID=...
CLOUDPAYMENTS_API_SECRET=...
GIFTLOOP_PREMIUM_PRICE_RUB=199

Configure the Pay notification URL as:

https://your-domain.example/webhooks/cloudpayments/pay

The webhook verifies Content-HMAC and then checks invoice ID, amount and currency before marking the payment paid.

## Core loop

1. Organizer creates a gift page.
2. GiftLoop generates a shareable URL.
3. Organizer shares it through WhatsApp, Telegram, Discord, email or SMS.
4. Friends contribute from the browser without signing up.
5. Contributors can become organizers for the next gift.

## Run locally

python -m venv .venv
.venv\\Scripts\\activate  # Windows
pip install -r requirements.txt
uvicorn app:app --reload

Open http://127.0.0.1:8000

Run tests with: pytest -q

## Security status

There are no user passwords or login accounts in this MVP. That removes the normal password-credential attack surface for contributors.

Owner tokens are generated with cryptographic randomness and only their SHA-256 hash is stored. Public gift responses do not expose the stored hash.

The app adds security headers, a rate limiter, a strict CSP and HSTS when served over HTTPS. Payment webhooks require HMAC verification.

Before production at meaningful scale, add HTTPS termination, managed secret storage, distributed rate limiting, audit logs, backups, dependency scanning, CSRF protection for future authenticated admin flows, secure session cookies, account recovery and MFA if accounts are introduced.
