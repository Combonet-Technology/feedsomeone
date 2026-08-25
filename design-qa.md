# Gallery retirement and gallery-administration design QA

- Source visual truth: `C:\Users\HP\AppData\Local\Temp\codex-clipboard-9cad97f6-5f85-4581-8715-5455decbfa08.png` (uneven Impact grid) and `C:\Users\HP\AppData\Local\Temp\codex-clipboard-3091536f-b111-4c45-93d2-031b64a8755d.png` (busy gallery backend)
- Rendered implementation: `http://localhost:8000/impact/`, `http://localhost:8000/events/2/feed-someone-2-0`, `http://localhost:8000/bcx/events/eventgalleryimage/`, and `/upload/`
- Viewport: 1400 x 800 for Impact; normal authenticated Chrome desktop viewport for admin
- State: standalone public Gallery retired; Impact detail retains on-demand images; compact gallery table and staged-upload review remain in the restricted admin

## Full-view comparison evidence

The public implementation resolves the uneven two-column rhythm shown in the supplied screenshot by using one flat 900px-wide list. The standalone Gallery navigation, footer block, homepage CTA and sitemap entry are removed; the legacy `/gallery/` address redirects permanently to Impact. Event photographs remain available where they carry the most context: inside each Impact detail record. The restricted admin retains the compact gallery table and separate batch uploader.

## Focused comparison evidence

Browser readback found no public Gallery navigation or footer heading, confirmed `/gallery/` resolves to the Impact list, and confirmed Feed Someone 2.0 still exposes `View images (8)`. The batch-review panel is mounted directly under `body` to escape Baton's transformed content shell, is capped at 80% of the viewport, and keeps its header and action bar outside the scrollable metadata list.

## Required fidelity surfaces

- Typography: existing Muli site font retained; headings reduced to 20px and metadata set to 16px bold, consistent with the reference hierarchy.
- Spacing and layout: one centred 900px list with 56px record spacing; the admin uses a dense table and a separate 1040px upload surface. The review dialog has clear space above and below it instead of reaching the site footer.
- Colours: existing OEF navy text on white retained; no new colour treatment introduced.
- Image quality: the reference contains no record imagery and the implementation adds none.
- Copy: database-backed impact titles, dates, locations and summaries remain unchanged; internal consent/privacy and grant-preparation wording is absent. The admin review uses event, additional tags and optional alt text only; caption fields are absent.

## Findings

No actionable P0, P1 or P2 visual differences remain in the implemented public Gallery retirement or the corrected uploader structure.

## Comparison history

- Initial Impact finding (P1): different record lengths created an uneven two-column composition.
- Impact fix: changed the record container to a single flat list while preserving the existing typography, public introduction and CTAs.
- Initial admin finding (P1): 16 images produced a long thumbnail/card wall with repeated dark caption, tag, publication and delete controls.
- Admin fix: introduced a database-backed table, moved upload to a separate staged flow, removed captions, and kept image previews only in the temporary review panel.
- Public Gallery retirement: removed its duplicated public discovery surface while preserving contextual Impact photographs and redirecting old bookmarks.
- Uploader overflow fix: moved the fixed dialog outside the transformed admin container, reduced its desktop height to 80dvh, and limited scrolling to the review body.

## Follow-up polish

The browser extension did not permit attaching a local test file during the visual pass. The full staged-upload interaction is covered by focused Django tests, including local staging, cancellation cleanup, confirmed Cloudinary handoff and database-index creation.

## Gallery retirement and uploader follow-up

- The standalone Gallery navigation, homepage CTA, footer block and sitemap entry are removed. `/gallery/` redirects permanently to Impact, while Feed Someone 2.0 still exposes `View images (8)` on its Impact detail page.
- The uploader review dialog is moved directly under `body` so Baton's transformed page container cannot size it against the page footer.
- The desktop dialog is capped at 80dvh. Its heading and Upload/Cancel bar remain fixed; only the metadata list scrolls.
- The compact table now exposes a provider-first `Mark selected images as public` bulk action. Failed Cloudinary updates remain private locally.
- The user retains the authenticated live tab for final acceptance testing; automated checks cover viewport rules, temporary-file cancellation, redirect behaviour and bulk-publication safety.

## Gallery retirement and uploader follow-up

- The standalone Gallery navigation, homepage CTA, footer block and sitemap entry are removed. `/gallery/` redirects permanently to Impact, while Feed Someone 2.0 still exposes `View images (8)` on its Impact detail page.
- The uploader review dialog is moved directly under `body` so Baton's transformed page container cannot size it against the page footer.
- The desktop dialog is capped at 80dvh. Its heading and Upload/Cancel bar remain fixed; only the metadata list scrolls.
- The compact table now exposes a provider-first `Mark selected images as public` bulk action. Failed Cloudinary updates remain private locally.
- The user retains the authenticated live tab for final acceptance testing; automated checks cover viewport rules, temporary-file cancellation, redirect behaviour and bulk-publication safety.

final result: passed
