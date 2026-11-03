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

## Reference v2 / mobile revision

- Framed ivory desktop canvas, compact navigation, matching font family served locally with its OFL license, a reconstructed panoramic hero and transparent product illustrations.
- Home features PuppyCare, CatLove, rope toy and pink bed from the existing catalogue; no nonexistent bone-snack SKU is invented.
- A separate mobile navigation pattern provides a menu drawer, bottom tabs and a filter drawer. Catalogues use the full available width instead of squeezing four columns alongside a permanent filter sidebar.
- Product detail, cart and checkout use dedicated narrow layouts. Checkout includes district in the address submitted to the API. Mobile form controls use 16px text to avoid unwanted focus zoom on iOS.
- Browser checks were performed on the actual local application at desktop width 1363px and narrow CSS viewport widths 454px and 340px (using browser zoom, not phone hardware emulation). Menu/filter open-close and product-to-cart-to-checkout navigation were exercised. No horizontal document overflow was observed in the checked pages. JS/CSS syntax checks, DOM/API fixture checks and the existing five API tests pass.
- The original design is a raster board, not a source design with exact fonts, components and original photography. The implementation follows its appearance closely; a literal 100% pixel identity is not claimed. No payment/shipping integration is implied by this visual revision.
- Additional generated assets: hero reconstruction based on the supplied homepage panel, and background extraction preserving the positions of all ten products in the existing atlas. The built-in image tool was used; final images are consumed directly by the frontend.

## Authentication form repair

The generic `.auth-form label` rule was overriding the icon-row layout, while the inner text input retained `width: 0`. Auth fields now have explicit visible labels, a scoped grid row and a full-width input. Mobile rows are 48px with 46px inputs at 16px font size; checkboxes are independently sized to 18px. Mobile `/login` and `/register` show only their selected form, with links to switch between them. Desktop retains the reference's side-by-side forms.

Browser geometry checks at 1363px, 454px and 340px verified nonzero input widths, correct row/checkbox heights, and no horizontal overflow; mobile tab switching was exercised. Existing API and DOM checks pass. This update does not enable social authentication or password recovery. The repository's self-hosted deployment workflow currently triggers only on `v*` tags; no tag or release is created by this repair.
