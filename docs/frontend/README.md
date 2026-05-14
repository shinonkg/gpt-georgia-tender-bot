# Frontend Notes

The current frontend is `index.html`.

## Key Concepts

- Static browser app.
- Supabase Auth gate.
- CSV/JSON data loading.
- Tender cards and detail drawer.
- Customer modal.
- Customer tender rows styled to resemble procurement portal rows.
- Main `Все тендеры` feed is loaded from `tenders.csv`; current product rule is announcement date from `01.03.2026`, all statuses, CPV `45100000`.
- Customer modal waits for `customer_tenders.csv` to finish loading before rendering the no-data state.

## AI Assistant Notes

- Keep `renderCustomerTenders()` compatible with `customer_tenders.csv`.
- Keep `loadData()` compatible with both old `tenders.csv` rows and the current `published` column.
- Keep drawer z-index above customer modal.
- Validate official link generation whenever tender URL fields change.
- Avoid large visual refactors unless requested.
