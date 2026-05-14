# Georgia Tender Monitor

AI-assisted tender tracking and monitoring dashboard for Georgian public procurement data, with a static frontend dashboard, Python scraping/monitoring bot, Supabase-backed review state, Telegram notifications, and Lago supplier tender integration.

> AI assistant note: this repository is currently a static dashboard plus Python automation. The requested Flask backend is a target architecture item, but no Flask application entrypoint is present in the current codebase.

## Project Overview

The project monitors tenders from `tenders.procurement.gov.ge`, stores extracted tender data in CSV/JSON files, renders an authenticated browser dashboard, and notifies operators when monitored suppliers such as Lago appear in new tender results.

Primary use cases:

- Track public tenders relevant to construction/site-preparation categories.
- Review tenders in a dashboard with cards, filters, detail drawers, and official tender links.
- Track historical tenders for monitored suppliers.
- Notify via Telegram when a monitored supplier has a newly detected tender participation.
- Keep data fresh through scheduled GitHub Actions runs.

## Features

| Feature | Status | Notes |
| --- | --- | --- |
| Tender dashboard | Active | Implemented in `index.html`. |
| Tender cards and detail drawer | Active | Main tenders and customer/Lago tenders use detail drawer behavior. |
| Supabase authentication | Active | Frontend uses Supabase Auth in browser. |
| Supabase review state | Active | Stores review status and notes for tenders. |
| Tender scraping | Active | Implemented in `georgia_tender_bot.py`. |
| Lago tender integration | Active | Uses supplier `monac_id=12891`; follows pagination for yearly results. |
| Official tender URLs | Active | Uses `https://tenders.procurement.gov.ge/public/?lang=ru&go={app_id}`. |
| Telegram notifications | Active | Sends a message when new customer tender rows are detected. |
| GitHub Actions automation | Active | Runs twice daily and can be triggered manually. |
| Flask backend | Planned | Documented as target backend layer; not currently implemented. |

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | HTML, CSS, vanilla JavaScript |
| Authentication | Supabase Auth |
| Database/state | Supabase table `tender_reviews` |
| Scraping | Python 3.11, Playwright, BeautifulSoup |
| Notifications | Telegram Bot API |
| Automation | GitHub Actions |
| Data files | `tenders.csv`, `customer_tenders.csv`, `tender_data.json` |
| Planned backend | Flask |

## Installation

1. Clone the repository.

```bash
git clone https://github.com/shinonkg/gpt-georgia-tender-bot.git
cd gpt-georgia-tender-bot
```

2. Install Python dependencies.

```bash
pip install -r requirements.txt
playwright install chromium
```

3. Configure environment variables.

```bash
export TELEGRAM_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"
export CUSTOMER_TENDER_YEAR="2026"
```

4. Run the scraper once.

```bash
python georgia_tender_bot.py --once
```

5. Open the dashboard.

For local static serving, use any simple web server:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000`.

## Environment Variables

| Variable | Required | Used by | Description |
| --- | --- | --- | --- |
| `TELEGRAM_TOKEN` | Yes for notifications | `georgia_tender_bot.py` | Telegram bot token. |
| `TELEGRAM_CHAT_ID` | Yes for notifications | `georgia_tender_bot.py` | Target Telegram chat/channel ID. |
| `CUSTOMER_TENDER_YEAR` | Optional | `georgia_tender_bot.py` | Year filter for customer tender searches. Defaults to current year. |
| Supabase URL/key | Currently inline in frontend | `index.html` | Supabase project credentials used by browser app. |

## Deployment

### GitHub Actions

The workflow in `.github/workflows/georgia-tender-bot.yml`:

- Runs at `05:00 UTC` and `17:00 UTC`.
- Can be started manually with `workflow_dispatch`.
- Installs Python dependencies and Playwright Chromium.
- Runs `python georgia_tender_bot.py --once`.
- Commits updated data files if changes exist.

### Static Dashboard

The dashboard is designed to be served as static files. If using GitHub Pages or another static host, publish:

- `index.html`
- `tenders.csv`
- `customer_tenders.csv`
- `tender_data.json`

## Folder Structure

```text
.
├── .github/workflows/georgia-tender-bot.yml
├── docs/
│   ├── backend/
│   ├── database/
│   ├── frontend/
│   └── integrations/
├── index.html
├── georgia_tender_bot.py
├── requirements.txt
├── tenders.csv
├── customer_tenders.csv
├── tender_data.json
├── README.md
├── SYSTEM_ARCHITECTURE.md
├── CURRENT_TASKS.md
├── BUGS.md
├── API_REFERENCE.md
└── CHANGELOG.md
```

## How The Tender System Works

1. `georgia_tender_bot.py` opens the Georgian procurement portal with Playwright.
2. It sends a search request to `/public/library/controller.php`.
3. It parses returned HTML rows with BeautifulSoup.
4. It extracts tender IDs, dates, organizer, budget, status, and official tender URLs.
5. It follows result pagination, including customer/Lago tender pages.
6. It writes data to CSV files consumed by the frontend.
7. The dashboard fetches CSV files and renders cards, filters, analytics, and detail drawers.

## How Telegram Notifications Work

Telegram notifications are triggered by customer tender synchronization:

1. The bot reads the existing `customer_tenders.csv`.
2. It fetches the latest customer tender list.
3. It compares `customer_id:tender_id` keys against existing rows.
4. New rows are sent to Telegram using `sendMessage`.
5. The CSV is rewritten so future runs do not alert for the same tender again.

## AI Coding Assistant Notes

- Treat `index.html` as the main frontend application.
- Treat `georgia_tender_bot.py` as the current backend/automation layer.
- Do not assume Flask exists until an app file such as `app.py` or `wsgi.py` is added.
- Main data contracts are the CSV headers in `tenders.csv` and `customer_tenders.csv`.
- Official tender links should use `/public/?lang=ru&go={app_id}`, not `/public/library/#/tenders/apinfo/{app_id}`.
- Lago uses `customer_id=424611441` and `monac_id=12891`.
- Preserve GitHub Actions behavior when changing generated data files.
