# Frontend reference update

The three supplied PawPaw design boards guide the cream background, mint/teal navigation, coral actions, compact cards, image treatment, storefront layouts and nine administration layouts.

## Implementation

- `frontend/static/design.js`: presentation templates and UI controls layered over the existing API client and event handlers. Authentication, authorization, product data, inventory and orders remain owned by the backend.
- `frontend/static/design.css`: reference palette, spacing, responsive storefront and administration layouts, focus states and reduced motion support.
- `frontend/static/index.html`: loads the presentation stylesheet and script after the original frontend. The single initialization call runs from `design.js` after both scripts have loaded.
- Static decorative artwork is stored in `frontend/static/assets/*.webp`. Ten illustrative product photographs are mapped by known seed slug with an emoji fallback; this does not change database records or invent stock, prices, reviews or orders.
- Customer order history and the administrator detail panel use returned API data. The confirmation receipt is saved only in the current browser session after a successful order API response. An arbitrary order code does not reveal customer data.
- Existing COD checkout, registration, login, service booking, returns, administration mutations and exports remain connected to the existing endpoints.
- Social sign-in, password recovery, staff selection, expanded settings and pet CRUD have no matching backend implementation. Their controls explain availability instead of simulating successful operations.

## Generated asset brief

Artwork was produced using the built-in image generator and exported to WebP for the website. The existing hero is retained.

1. Decorative atlas: six equal cells, golden puppy with cream kitten, puppy in pink grooming towel, cream cat with stethoscope, pets on beige blanket, Vietnamese grooming/vet staff, hand-drawn cuddling dog/cat mascot. Soft golden daylight; warm ivory, mint and coral palette; no UI or text. Exported as `pet-duo`, `grooming`, `vet-cat`, `pet-blanket`, `staff`, and `mascot`.
2. Product atlas: ten individual studio illustrations of turquoise PuppyCare pouch, pink CatLove pouch, RoyalDog can, CatMenu cans, pink donut bed, rope ball, fish plush, cat house, shampoo and coral harness. Soft ivory background, isolated products and natural shadows. Exported under `assets/products/`.
3. PuppyCare lifestyle: golden puppy on the left, turquoise PuppyCare pouch on the right, beige kibble bowl in the foreground, soft sunlit cream room.

Generated product illustrations are visual placeholders for the seed catalogue. New catalogue items retain their configured symbol until a media API or explicit static mapping is supplied.

## Validation and limits

- Existing Python API tests pass (5 tests).
- JavaScript syntax checks pass.
- Frontend DOM checks use fixtures returned by the actual FastAPI application: public and populated cart/checkout/favorites routes, nine administrator routes, order detail, customer order history and FAQ filtering.
- WebP integrity and static asset references are checked.
- Managed preview could not start: the preview relay is unavailable. Browser layout, responsive screenshots and a pixel comparison against the boards remain unverified. No claim of a 100% pixel match is made.
- These changes update GitHub source; they do not deploy AWS infrastructure.
