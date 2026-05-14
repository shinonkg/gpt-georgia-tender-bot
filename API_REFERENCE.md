# API Reference

This project consumes external APIs and file-based data contracts. A Flask API is planned but not currently implemented in this repository.

> AI assistant note: when adding Flask endpoints, update this file in the same commit.

## External Procurement Portal

Base URL:

```text
https://tenders.procurement.gov.ge
```

### GET `/public/?lang=en`

Loads the public procurement portal and establishes browser/session context.

| Field | Value |
| --- | --- |
| Method | `GET` |
| Auth | Public |
| Used by | `georgia_tender_bot.py` |

Example:

```http
GET /public/?lang=en HTTP/1.1
Host: tenders.procurement.gov.ge
```

### POST `/public/library/controller.php`

Searches tenders.

| Field | Value |
| --- | --- |
| Method | `POST` |
| Auth | Public browser session |
| Content-Type | `application/x-www-form-urlencoded; charset=UTF-8` |
| Used by | `fetch_customer_tenders_playwright()` |

Request body example for Lago 2026:

```text
action=search_app
app_t=0
search=
app_reg_id=
app_shems_id=0
org_a=
app_monac_id=12891
org_b=lago
app_particip_status_id=0
app_donor_id=0
app_status=0
app_agr_status=0
app_type=0
app_basecode=0
app_codes=
app_date_type=1
app_date_from=01.01.2026
app_date_tlll=31.12.2026
app_amount_from=
app_amount_to=
app_currency=2
app_pricelist=0
```

Response example:

```html
<tr id="A680266">
  ...
  Announcment number: <strong>NAT260006413</strong>
  Procurement announcment date: 30.03.2026
  Offer reception term: 20.04.2026
</tr>
<div class="pager">6 Record(s) (page: 1/2)</div>
```

Error responses:

| Status | Meaning | Handling |
| --- | --- | --- |
| Non-200 | Portal error or blocked request | Log warning/error and skip update. |
| 200 empty body | Search returned no data or session issue | Log warning and preserve previous CSV. |

### GET `/public/library/controller.php?action=search_app&page={page}`

Fetches subsequent search result pages after the initial POST stores search state in the session.

| Field | Value |
| --- | --- |
| Method | `GET` |
| Auth | Same browser/session as initial POST |
| Used by | Customer tender pagination |

Example:

```http
GET /public/library/controller.php?action=search_app&page=2 HTTP/1.1
Host: tenders.procurement.gov.ge
```

## Official Tender URLs

Official tender detail pages should be linked with:

```text
https://tenders.procurement.gov.ge/public/?lang=ru&go={app_id}
```

Avoid:

```text
https://tenders.procurement.gov.ge/public/library/#/tenders/apinfo/{app_id}
```

The `apinfo` form can return `File not found`.

## Telegram Bot API

Base URL:

```text
https://api.telegram.org/bot{TELEGRAM_TOKEN}
```

### POST `/sendMessage`

Sends new customer tender notifications.

| Field | Value |
| --- | --- |
| Method | `POST` |
| Auth | Bot token in URL |
| Used by | `send_telegram_message()` |

Request JSON:

```json
{
  "chat_id": "123456789",
  "text": "<b>Yeni musteri ihalesi bulundu</b>\nFirma: <b>Lago</b>\nIhale: <b>NAT260006413</b>",
  "parse_mode": "HTML",
  "disable_web_page_preview": true
}
```

Success response example:

```json
{
  "ok": true,
  "result": {
    "message_id": 1
  }
}
```

Error response example:

```json
{
  "ok": false,
  "error_code": 401,
  "description": "Unauthorized"
}
```

## Supabase APIs

The frontend uses Supabase JavaScript client directly.

### Auth Session

| Operation | Purpose |
| --- | --- |
| `supabase.auth.getSession()` | Checks whether dashboard user is authenticated. |
| `supabase.auth.signInWithPassword()` | Logs user in. |
| `supabase.auth.signOut()` | Logs user out. |

### Table: `tender_reviews`

| Operation | Purpose |
| --- | --- |
| `select("*")` | Load review status and notes. |
| `upsert({ tender_id, review_status, note })` | Save review status and note. |

Example upsert:

```js
await supabaseClient
  .from("tender_reviews")
  .upsert({
    tender_id: "NAT260009720",
    review_status: "review",
    note: "Check documents"
  }, { onConflict: "tender_id" });
```

## File Data Contracts

### GET `tenders.csv`

Loaded by browser dashboard.

```text
date_found,last_seen,id,reg_id,name,org,price,deadline,status,cpvs,label,attachment_count,pdf_count,excel_count,image_count,link
```

### GET `customer_tenders.csv`

Loaded by customer modal.

```text
customer_id,customer_name,tender_id,title,organizer,budget,currency,status,publish_date,deadline,url
```

### GET `tender_data.json`

Reserved for structured tender data.

Placeholder response:

```json
{
  "updated_at": "2026-05-14T00:00:00Z",
  "items": []
}
```

## Planned Flask API

No Flask endpoints exist yet. Suggested future API:

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Health check. |
| `GET` | `/api/tenders` | Return main tenders as JSON. |
| `GET` | `/api/customers/{customer_id}/tenders` | Return customer tender history. |
| `POST` | `/api/sync` | Trigger manual sync. |
| `POST` | `/api/telegram/test` | Send test Telegram message. |

Authentication notes:

- Use Supabase JWT or server-side session validation before exposing write or sync endpoints.
- Never expose `TELEGRAM_TOKEN` to the browser.
