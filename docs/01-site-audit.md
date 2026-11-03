# 01 · Site audit — PawPaw Pet Shop

Source: the three user-provided UI boards in `references/`. They are design screenshots, not a public live website, so only visible UI is treated as observed behavior.

## Evidence inventory

| Area | Requirement | Classification | Confidence / evidence |
|---|---|---|---|
| Storefront | Hero, categories, featured product cards, service promotions | Observed | High — storefront board, home view |
| Product catalog | Search, category/species filters, sort, stock and price | Observed | High — catalog view |
| Product detail | Gallery, variants, price, rating, add-to-cart | Observed | High — product view |
| Cart and checkout | Quantity changes, coupon, shipping, customer address, payment choice | Observed | High — cart and checkout views |
| Account | Login/register, saved products, orders, pet profiles | Observed | High — account and authentication views |
| Order tracking | Confirmation and shipping status timeline | Observed | High — order confirmation view |
| Service booking | Grooming/vet, pet, date, time, staff, note | Observed | High — booking view |
| Customer support | FAQ, contact, shipping/returns, return request | Observed | High — support view |
| Admin | Dashboard, order/product/customer/inventory/promotions/service/report/settings screens | Observed | High — 9-screen admin board |
| Payments | COD appears in design; cards/wallets shown visually | Observed / inferred | Medium — checkout board; no provider credentials or webhook behavior supplied |
| Logistics | Carrier/tracking UI shown | Observed / inferred | Medium — tracking view; no shipping API/provider supplied |
| Admin staff permissions | Role management is shown in settings | Observed / proposed | Medium — UI shows settings, but detailed permissions are not provided |

## Proposed MVP scope

- Storefront: home, catalog/search/filter, product detail, local cart, checkout, order confirmation/lookup, account login/register, favorites, service appointment, support and return request.
- Admin: dashboard, order status, product CRUD, stock adjustment, customers, coupons, bookings, reports and store settings.
- Seed data is clearly demo data. COD is the only active payment method. Bank transfer, card/wallet payments, carrier integrations and email delivery require credentials/configuration.
- One admin account and customer role; staff role granularity, real pet profile CRUD, reviews, CMS/blog publishing and notifications are Phase 2.

## Acceptance journeys

1. Browse/search → product → add to cart → place COD order → inventory decrements in the same database transaction → lookup the order by code and phone.
2. Register/login → see account order list → logout; admin routes reject customer accounts.
3. Request grooming/vet slot → reject duplicate staff/time reservation → admin confirms or completes booking.
4. Admin searches and updates orders/products/inventory/coupons/settings; dashboards and reports use persisted records.
5. Submit return request against an existing order and phone number; admin review workflow is recorded.

## Non-functional assumptions and boundaries

- Initial scale: small shop / pilot, low write concurrency, single AWS region and one VM.
- Availability target: best-effort MVP; a single Lightsail instance is not highly available.
- Sensitive data: names, phones, addresses, hashed passwords. TLS, HTTP-only sessions, role checks, limited logging and local encrypted-at-rest volume are future operational checks; backups must be enabled before real orders.
- Currency: VND integer units. All instants are stored as UTC strings; appointment date/time are local shop schedule fields.
- The mockup board is not used as a full-page background. UI is built from reusable HTML/CSS components and generated pet imagery.
