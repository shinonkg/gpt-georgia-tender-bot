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
- `tender_data.json`: structured copy of the main tender feed.

Current `tenders.csv` headers:

```text
date_found,last_seen,id,reg_id,published,name,org,price,deadline,status,cpvs,label,attachment_count,pdf_count,excel_count,image_count,link
```

Current `customer_tenders.csv` headers:

```text
customer_id,customer_name,tender_id,title,organizer,budget,currency,status,publish_date,deadline,url
```

## AI Assistant Notes

- Treat CSV headers as public data contracts.
- Keep `published` available for main tender detail drawers and announcement-date filtering.
- Update this folder if Supabase schema changes.
- Confirm RLS policies before moving sensitive operations to frontend code.
