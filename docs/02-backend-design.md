# 02 · Backend design

## Architecture

Modular monolith: FastAPI routes → application/domain services → SQLite repository adapter. Static frontend is a separate deployable directory and only talks to `/api/*`. SQLite is chosen for a low-concurrency pilot on one Lightsail VM and no managed-database bill. Move to PostgreSQL before meaningful concurrent production traffic or multi-instance deployment.

## Actors and access

| Actor | Allowed actions |
|---|---|
| Guest | Read catalog/FAQ; submit COD order, appointment and return request; look up order using code + phone |
| Customer | Guest actions plus view their own account/orders; session is a random, hashed server-side token in an HTTP-only cookie |
| Admin | All `/api/admin/*` operations; verified on every endpoint by role. Customer identifiers and address are returned only to admin or matching order lookup |

Cookie mutations require a same-site CSRF token. Passwords are PBKDF2-SHA256 salted hashes. Login is throttled in-process. Production must use a strong `APP_SECRET`, a unique admin password and HTTPS. This is a single-process MVP; shared/distributed rate limits and richer staff RBAC are future work.

## Domain modules and invariants

- Catalog: active product reads, search, species/category filters, stable sort; prices and stock come from the server.
- Orders: server reloads every product/price, validates quantities and stock, computes coupon/shipping/total, inserts order/items, decrements stock and consumes coupon in one `BEGIN IMMEDIATE` transaction. VND values are integers.
- Order state: pending → confirmed → preparing → shipping → delivered; cancellation is allowed before shipping. Invalid transitions return 409.
- Inventory: nonzero signed stock adjustments, no negative stock, an immutable event row per adjustment.
- Booking: validated grooming/vet request; database uniqueness prevents the same staff/date/time slot from being reserved twice.
- Promotions: bounded discount values, minimum subtotal and usage limit checked server-side.
- Returns: order must match code + phone; status starts requested. Refund execution is not wired to a payment processor.
- Auth: server-side role check on every protected resource; no trust in frontend flags.

## API surface

OpenAPI contract is in `contracts/openapi.yaml`; interactive docs are available at `/api/docs` in non-production.

| Method + path | Role | Use |
|---|---|---|
| GET `/api/health`, `/api/csrf`, `/api/storefront/settings` | Public | Health, CSRF bootstrap and public checkout settings |
| GET `/api/products`, `/api/products/{slug}` | Public | Catalog/detail |
| POST `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`; GET `/api/auth/me` | Public/session | Account and secure session lifecycle |
| POST `/api/orders`; GET `/api/orders/lookup`, `/api/account/orders` | Public/customer | Checkout, order lookup and owned orders |
| POST `/api/bookings`; GET `/api/faqs`; POST `/api/returns` | Public | Service, support, return requests |
| GET `/api/admin/dashboard`, `/orders`, `/products`, `/customers`, `/promotions`, `/appointments`, `/reports`, `/settings` | Admin | Admin reads |
| POST/PATCH `/api/admin/products`, `/orders/{id}`, `/appointments/{id}`, `/promotions`, `/inventory`, `/settings` | Admin | Admin writes |

## Errors, abuse controls and observability

Errors use standard HTTP status + `{detail}`. Inputs are validated at the API boundary and again by database constraints. Login attempts are limited; all unsafe browser forms use CSRF. Do not log passwords, cookie values, full addresses or payment secrets. Production reverse proxy should terminate TLS and forward request IDs. Add structured logs, metrics, centralized rate limits and audit events before public launch.

## Integrations deliberately left as adapters

- Payments: COD works; online payments are disabled until the selected Vietnam provider merchant account, signing secret, return URL and webhook endpoint are configured. Never mark an order paid from a browser redirect alone.
- Delivery: carrier tracking UI is prepared, but provider booking/webhook calls are not configured.
- Email/SMS: confirmation is on-screen; outbound notification credentials are absent.
- Media: generated hero file is local. Product cards use simple illustrative symbols until licensed catalog photographs are supplied.
