# Georgia Tender Monitor

AI-assisted tender tracking and monitoring dashboard for Georgian public procurement data, with a static frontend dashboard, Python scraping/monitoring bot, Supabase-backed review state, Telegram notifications, and monitored supplier tender integration.

> AI assistant note: this repository is currently a static dashboard plus Python automation. The requested Flask backend is a target architecture item, but no Flask application entrypoint is present in the current codebase.

## Project Overview

The project monitors tenders from `tenders.procurement.gov.ge`, stores extracted tender data in CSV/JSON files, renders an authenticated browser dashboard, and notifies operators when monitored suppliers appear in new tender results.

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
| Tender cards and detail drawer | Active | Main tenders and monitored supplier tenders use detail drawer behavior. |
| Supabase authentication | Active | Frontend uses Supabase Auth in browser. |
| Supabase review state | Active | Stores review status and notes for tenders. |
| Tender scraping | Active | Implemented in `georgia_tender_bot.py`. |
| Monitored supplier integration | Active | Tracks Lago, Our Group, Ander Konstrakshen, Eplaini, Jorjia Bilding Grupi, Kualiti, Legu Bildingi, SG Jgupi, and Regrini; follows pagination for yearly results. |
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
| Refresh helpers | Node.js scripts in `scripts/` |
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

## Testing

Run the local Node parser tests:

```bash
node --test
```

## Environment Variables

| Variable | Required | Used by | Description |
| --- | --- | --- | --- |
| `TELEGRAM_TOKEN` | Yes for notifications | `georgia_tender_bot.py` | Telegram bot token. |
| `TELEGRAM_CHAT_ID` | Yes for notifications | `georgia_tender_bot.py` | Target Telegram chat/channel ID. |
| `CUSTOMER_TENDER_YEAR` | Optional | `georgia_tender_bot.py` | Year filter for customer tender searches. Defaults to current year. |
| `CUSTOMER_TENDER_DATE_TYPE` | Optional | `georgia_tender_bot.py` | Procurement portal date filter. Defaults to `2`, the offer reception/auction date, so late previous-year announcements with current-year participation are included. |
| `MAIN_TENDER_DATE_FROM` | Optional | `scripts/refresh_tenders.mjs` | Main dashboard announcement-date lower bound. Defaults to `01.03.2026`. |
| `MAIN_TENDER_DATE_TILL` | Optional | `scripts/refresh_tenders.mjs` | Main dashboard announcement-date upper bound. Defaults to `31.12.2026`. |
| `MAIN_TENDER_BASECODE` | Optional | `scripts/refresh_tenders.mjs` | Procurement category base code. Defaults to `18999`, the portal ID for CPV `45100000`. |
| Supabase URL/key | Currently inline in frontend | `index.html` | Supabase project credentials used by browser app. |

## Deployment

### GitHub Actions

The workflow in `.github/workflows/georgia-tender-bot.yml`:

- Runs at `05:00 UTC` and `17:00 UTC`.
- Can be started manually with `workflow_dispatch`.
- Installs Python dependencies and Playwright Chromium.
- Runs `python georgia_tender_bot.py --once`.
- Runs `node scripts/refresh_tenders.mjs` to refresh the main dashboard feed.
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
2. It synchronizes monitored supplier participation into `customer_tenders.csv`.
3. `scripts/refresh_tenders.mjs` refreshes the main dashboard tender feed.
4. Both refresh paths send search requests to `/public/library/controller.php`.
5. They parse returned HTML rows, extract tender IDs, dates, organizer, budget, status, and official tender URLs.
6. They follow result pagination and write CSV/JSON files consumed by the frontend.
7. The dashboard fetches CSV files and renders cards, filters, analytics, and detail drawers.

## Main Tender Feed Rules

The main `Все тендеры` dashboard feed is generated by `scripts/refresh_tenders.mjs`.

- Uses procurement `app_date_type=1`, announcement date.
- Defaults to `MAIN_TENDER_DATE_FROM=01.03.2026`.
- Includes all procurement statuses with `app_status=0`.
- Defaults to portal base category `18999`, equivalent to CPV `45100000`.
- Writes both `tenders.csv` and `tender_data.json`.

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
- Monitored supplier IDs: Lago `12891`, Our Group chveni jgupi `36827`, Ander Konstrakshen `104814`, Eplaini `71057`, Jorjia Bilding Grupi `83472`, Kualiti `77262`, Legu Bildingi `115620`, SG Jgupi `79247`, Regrini `129219`.
- Main tender dashboard feed should include all statuses from announcement date `01.03.2026` onward unless the product requirement changes.
- Preserve GitHub Actions behavior when changing generated data files.
