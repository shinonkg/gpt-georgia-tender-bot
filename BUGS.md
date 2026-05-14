# Bugs

This file tracks known issues, reproduction steps, workarounds, and investigation notes.

## Severity Labels

| Label | Meaning |
| --- | --- |
| `S0` | Critical outage or data loss. |
| `S1` | Major feature broken. |
| `S2` | Noticeable bug with workaround. |
| `S3` | Minor issue or polish. |

## Known Issues

### S1: Local Python command resolves to Microsoft Store alias

**Status:** Open  
**Area:** Development environment

**Steps to reproduce**

1. Run `python --version` on the current Windows machine.
2. Observe Microsoft Store alias error.

**Expected**

Python version is printed.

**Actual**

Windows reports Python was not found.

**Workaround**

- Use GitHub Actions Python 3.11 environment for production runs.
- Install Python locally or disable the Microsoft Store execution alias.

**Investigation notes**

- The workflow uses `actions/setup-python@v5`, so scheduled automation should still have Python.

### S2: Frontend depends on CSV shape and inline string templates

**Status:** Open  
**Area:** Frontend

**Steps to reproduce**

1. Change a CSV header or quoted field behavior.
2. Reload dashboard.
3. Customer tender cards may show missing values if header names change.

**Workaround**

- Preserve current headers.
- Add compatibility mapping in `loadCustomerTendersCSV()` before changing generated CSV.

**Investigation notes**

- `customer_tenders.csv` now uses properly quoted CSV fields.
- The frontend parser must continue handling quoted strings.

### S2: Flask backend is documented but not implemented

**Status:** Open  
**Area:** Backend

**Steps to reproduce**

1. Search for `app.py`, `wsgi.py`, or Flask imports.
2. No Flask application is present.

**Workaround**

- Treat `georgia_tender_bot.py` as the current backend automation layer.
- Add Flask only when API serving becomes necessary.

**Investigation notes**

- Documentation marks Flask as planned/target architecture to avoid confusing future AI sessions.

### S3: Mixed language/encoding display in terminal

**Status:** Open  
**Area:** Developer tooling

**Steps to reproduce**

1. Read UTF-8 files through PowerShell with default code page.
2. Some Cyrillic/Turkish/emoji text may appear as mojibake.

**Workaround**

- Use UTF-8-aware editor.
- Avoid unnecessary text rewrites.
- Prefer ASCII for new log messages if encoding is uncertain.

## Resolved Issues

| Date | Severity | Issue | Fix |
| --- | --- | --- | --- |
| 2026-05-14 | S1 | Official customer tender links opened `File not found`. | Normalize links to `/public/?lang=ru&go={app_id}`. |
| 2026-05-14 | S1 | Lago showed only four tenders. | Added pagination handling and refreshed CSV to six 2026 records. |
| 2026-05-14 | S2 | Customer tender drawer opened behind Lago modal. | Raised drawer z-index above customer modal. |

## Bug Report Template

```markdown
### S?: Short title

**Status:** Open
**Area:** Frontend | Backend | Database | Integrations | Deployment

**Steps to reproduce**
1.
2.
3.

**Expected**

**Actual**

**Workaround**

**Investigation notes**
```
