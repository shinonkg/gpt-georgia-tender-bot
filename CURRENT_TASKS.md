# Current Tasks

This file tracks active work for humans and AI coding assistants.

## Priority Labels

| Label | Meaning |
| --- | --- |
| `P0` | Critical production issue. |
| `P1` | High priority user-facing work. |
| `P2` | Important improvement. |
| `P3` | Nice-to-have or cleanup. |

## In Progress

| Priority | Task | Owner | Notes |
| --- | --- | --- | --- |
| P1 | Stabilize Lago tender monitoring | AI/Human | Pagination is implemented; monitor next scheduled run. |
| P2 | Improve documentation coverage | AI | Initial documentation set created. |

## Pending

| Priority | Task | Area | Acceptance Criteria |
| --- | --- | --- | --- |
| P1 | Verify Telegram alerts in GitHub Actions | Integrations | A new test tender or controlled CSV diff sends exactly one Telegram message. |
| P1 | Confirm Supabase schema | Database | `tender_reviews` columns and RLS policy documented. |
| P2 | Add Flask backend if required | Backend | Flask app exposes documented API routes and does not break static deployment. |
| P2 | Add automated parser tests | Backend | HTML fixtures validate pagination, NAT extraction, dates, organizer, and budget. |
| P2 | Add frontend smoke test | Frontend | Dashboard loads CSVs and opens tender/customer drawers. |
| P3 | Split `index.html` into modules | Frontend | Preserve current behavior while improving maintainability. |

## Completed

| Date | Task | Notes |
| --- | --- | --- |
| 2026-05-14 | Customer tender detail drawer | Lago tenders can open the shared detail drawer. |
| 2026-05-14 | Official tender URL fix | Converted `apinfo/{id}` links to `public/?lang=ru&go={id}`. |
| 2026-05-14 | Lago pagination | Bot follows result pages and loads all 2026 Lago tender rows. |
| 2026-05-14 | Telegram new-entry detection | Compares current customer CSV against previous CSV before sending alerts. |
| 2026-05-14 | Drawer z-index fix | Tender drawer appears above customer modal. |

## Technical Debt

| Priority | Debt | Suggested Fix |
| --- | --- | --- |
| P1 | Python validation not available on local Windows alias | Run checks in CI or install Python locally. |
| P2 | Single large `index.html` | Split into `assets/js`, `assets/css`, and templates when build tooling exists. |
| P2 | CSV parsing in frontend is hand-rolled | Keep tests around quoted fields; consider a small parser library if bundling is introduced. |
| P2 | Supabase credentials appear frontend-side | Confirm this is acceptable for public anon key usage and RLS rules. |
| P3 | Mixed language labels | Standardize UI copy or document intentional Russian/Turkish/English mix. |

## AI Assistant Notes

- Start with `README.md` and `SYSTEM_ARCHITECTURE.md`.
- Before changing parser logic, inspect a fresh procurement HTML response.
- Before changing dashboard UI, verify that `customer_tenders.csv` quoted rows still render correctly.
- Keep changes small because the frontend has many inline string templates.
