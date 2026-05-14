# Integration Notes

## Procurement Portal

Base URL:

```text
https://tenders.procurement.gov.ge
```

The scraper uses:

- `GET /public/?lang=en`
- `POST /public/library/controller.php`
- `GET /public/library/controller.php?action=search_app&page={page}`

Current search semantics:

- Main dashboard feed: `app_date_type=1`, announcement date from `01.03.2026`, `app_status=0`, `app_basecode=18999`.
- Monitored supplier feed: defaults to `app_date_type=2`, so current-year participation can include late previous-year announcements.
- Supplier autocomplete IDs were resolved through `library/list_org.php?orgtype=1`.

## Telegram

Telegram alerts use `sendMessage` with HTML parse mode.

Required secrets:

- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`

## GitHub Actions

The scheduled workflow runs twice daily, executes the Python supplier sync, executes `node scripts/refresh_tenders.mjs`, and commits changed data files.

## AI Assistant Notes

- Procurement portal HTML is not a stable formal API; re-check selectors when parsing breaks.
- Official URLs should use `/public/?lang=ru&go={app_id}`.
- Never commit Telegram secrets.
- Preserve pagination for both main and supplier feeds.
