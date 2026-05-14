# Changelog

All notable changes to this project should be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) style and uses semantic versioning once releases are introduced.

## [Unreleased]

### Added

- AI-friendly project documentation set.
- `/docs` folder structure for frontend, backend, database, and integrations notes.

### Changed

- Placeholder for future changes.

### Fixed

- Placeholder for future fixes.

### Removed

- Placeholder for future removals.

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
