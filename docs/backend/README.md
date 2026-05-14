# Backend Notes

The current backend behavior is implemented by `georgia_tender_bot.py`.

## Current Responsibilities

- Launch Playwright Chromium.
- Search procurement portal.
- Parse HTML rows with BeautifulSoup.
- Follow pagination.
- Write CSV data files.
- Send Telegram alerts for newly detected customer tender rows.

## Planned Flask Responsibilities

- Serve JSON APIs.
- Trigger manual sync jobs.
- Hide sensitive integration tokens from the browser.
- Provide health checks and operational endpoints.

## AI Assistant Notes

- Do not assume Flask exists yet.
- If adding Flask, document routes in `API_REFERENCE.md`.
- Preserve GitHub Actions compatibility.
