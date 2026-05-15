# Changelog

All notable changes to this project should be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) style and uses semantic versioning once releases are introduced.

## [Unreleased]

### Added

- AI-friendly project documentation set.
- `/docs` folder structure for frontend, backend, database, and integrations notes.
- `scripts/refresh_tenders.mjs` for the main `Все тендеры` dashboard feed.
- `scripts/refresh_customer_tenders.mjs` as a local Node helper for monitored supplier CSV refreshes.
- Shared procurement parser helpers and fixture-based Node tests for tender HTML parsing.
- Five monitored suppliers: Jorjia Bilding Grupi, Kualiti, Legu Bildingi, SG Jgupi, and Regrini.

### Changed

- Main tender feed now includes all statuses for CPV `45100000` from announcement date `01.03.2026` onward.
- GitHub Actions now refreshes the main tender feed after the Python monitored-supplier sync.
- `customer_tenders.csv` now includes Lago, Our Group chveni jgupi, Ander Konstrakshen, and Eplaini.
- Supplier tender search defaults to `app_date_type=2` to include current-year participation even when announcement date is in the previous year.
- Node refresh scripts now use the same parser module for page-count extraction, row parsing, CSV quoting, and official URL construction.

### Fixed

- Customer modal now waits for `customer_tenders.csv` loading before showing an empty/no-data state.
- Tender detail drawer now shows a clearer summary, normalized official links, and safer escaped content.
- Main dashboard no longer depends on a stale hand-curated `tenders.csv` with only active announced rows.

## [0.3.0] - 2026-05-14

### Added

- Lago customer tender pagination support.
- Telegram notification logic for newly detected customer tenders.
- Current-year customer tender filtering with `CUSTOMER_TENDER_YEAR` override.

### Changed

- `customer_tenders.csv` now includes all fetched 2026 Lago rows and normalized official URLs.

### Fixed

- Lago tender list no longer stops at the first portal page.

## [0.2.0] - 2026-05-14

### Added

- Customer tender detail drawer.
- Customer tender card actions for details and official site.
- Official URL normalization helper in frontend.

### Changed

- Lago tenders were restyled into a portal-like row layout using dashboard colors.

### Fixed

- Customer tender official links no longer use broken `apinfo` URL format.
- Tender drawer now appears above customer modal.

## [0.1.0] - Initial

### Added

- Static dashboard in `index.html`.
- Python tender monitoring script.
- GitHub Actions workflow.
- CSV/JSON data files.
- Supabase-authenticated review workflow.
