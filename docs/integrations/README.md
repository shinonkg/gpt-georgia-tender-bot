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

## Telegram

Telegram alerts use `sendMessage` with HTML parse mode.

Required secrets:

- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`

## GitHub Actions

The scheduled workflow runs twice daily and commits changed data files.

## AI Assistant Notes

- Procurement portal HTML is not a stable formal API; re-check selectors when parsing breaks.
- Official URLs should use `/public/?lang=ru&go={app_id}`.
- Never commit Telegram secrets.
