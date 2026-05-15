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
| P1 | Verify scheduled data refresh after latest workflow changes | AI/Human | Confirm GitHub Actions updates both main tenders and monitored supplier tenders. |

## Pending

| Priority | Task | Area | Acceptance Criteria |
| --- | --- | --- | --- |
| P1 | Verify Telegram alerts in GitHub Actions | Integrations | A new test tender or controlled CSV diff sends exactly one Telegram message. |
| P1 | Confirm Supabase schema | Database | `tender_reviews` columns and RLS policy documented. |
| P2 | Add Flask backend if required | Backend | Flask app exposes documented API routes and does not break static deployment. |
| P2 | Add frontend smoke test | Frontend | Dashboard loads CSVs and opens tender/customer drawers. |
| P2 | Confirm main tender feed business filters | Data | Current rule is announcement date >= 01.03.2026, all statuses, CPV 45100000. |
| P3 | Split `index.html` into modules | Frontend | Preserve current behavior while improving maintainability. |

## Completed

| Date | Task | Notes |
| --- | --- | --- |
| 2026-05-14 | Customer tender detail drawer | Lago tenders can open the shared detail drawer. |
| 2026-05-14 | Official tender URL fix | Converted `apinfo/{id}` links to `public/?lang=ru&go={id}`. |
| 2026-05-14 | Lago pagination | Bot follows result pages and loads all 2026 Lago tender rows. |
| 2026-05-14 | Telegram new-entry detection | Compares current customer CSV against previous CSV before sending alerts. |
| 2026-05-14 | Drawer z-index fix | Tender drawer appears above customer modal. |
| 2026-05-14 | Expanded monitored suppliers | Added Our Group, Ander Konstrakshen, and Eplaini supplier tender history. |
| 2026-05-14 | Customer tender load race fix | Customer modal waits for `customer_tenders.csv` before showing no-data state. |
| 2026-05-14 | Main tender feed refresh | `Все тендеры` now uses announcement date from 01.03.2026, all statuses, CPV 45100000. |
| 2026-05-14 | GitHub Actions main-feed refresh | Workflow now runs `scripts/refresh_tenders.mjs` after the Python supplier sync. |
| 2026-05-15 | Automated parser tests | Node fixture tests validate pagination, NAT extraction, dates, organizer, budget, CSV quoting, and official URLs. |
| 2026-05-15 | Expanded monitored suppliers | Added Jorjia Bilding Grupi, Kualiti, Legu Bildingi, SG Jgupi, and Regrini to scraper, Node helper, and dashboard. |

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
