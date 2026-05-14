# Backend Notes

The current backend behavior is implemented by `georgia_tender_bot.py` plus Node.js refresh helpers in `scripts/`.

## Current Responsibilities

- Launch Playwright Chromium.
- Search procurement portal.
- Parse HTML rows with BeautifulSoup.
- Follow pagination.
- Write monitored supplier CSV data.
- Send Telegram alerts for newly detected customer tender rows.
- Refresh the main dashboard feed through `scripts/refresh_tenders.mjs`.
- Provide local Windows-friendly refresh helpers where Python is unavailable.

## Current Refresh Boundaries

| File | Purpose |
| --- | --- |
| `georgia_tender_bot.py` | Monitored supplier history and Telegram alerts. |
| `scripts/refresh_tenders.mjs` | Main `Все тендеры` feed, announcement date from `01.03.2026`, all statuses, CPV `45100000`. |
| `scripts/refresh_customer_tenders.mjs` | Local helper mirroring monitored supplier CSV refresh behavior. |

## Planned Flask Responsibilities

- Serve JSON APIs.
- Trigger manual sync jobs.
- Hide sensitive integration tokens from the browser.
- Provide health checks and operational endpoints.

## AI Assistant Notes

- Do not assume Flask exists yet.
- If adding Flask, document routes in `API_REFERENCE.md`.
- Preserve GitHub Actions compatibility.
- Keep main-feed and supplier-feed date semantics explicit; they intentionally differ.
