# Database Notes

The project currently uses both Supabase and file-based data.

## Supabase

Known table:

```text
tender_reviews(tender_id, review_status, note)
```

Additional schema details should be confirmed from the Supabase project.

## File Data

- `tenders.csv`: main tender feed.
- `customer_tenders.csv`: customer/supplier tender history.
- `tender_data.json`: structured tender data placeholder/feed.

## AI Assistant Notes

- Treat CSV headers as public data contracts.
- Update this folder if Supabase schema changes.
- Confirm RLS policies before moving sensitive operations to frontend code.
