# CHS Complaint Dashboard (Python edition)

## Run locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Upload the daily `.xlsx` or `.csv` export in the browser tab. The app runs locally, checks required headers (case-insensitive and ignoring spaces/underscores), removes listed PII columns immediately after parsing, and computes metrics from the uploaded file. The app does not create synthetic data or persist the uploaded rows.

## SLA definitions

- **A · Deadline (default):** compare closing timestamp (or created timestamp for pending rows) with the SLA deadline; a missing deadline is recalculated from creation plus SLA hours.
- **B · System status:** `COMPLAINT_STATUS_AS_ON_SELECTED_DATE` ends in `BEYOND`.
- **C · Reported duration:** computed elapsed hours exceed SLA hours; starred overflow durations are counted as breaches. The raw duration field is not treated as a numeric duration.

The reconciliation card shows all three counts and the number of rows where they disagree. Edit the `ALIASES` dictionary near the top of `app.py` to add normalized spelling corrections.

## Scope note

This is a Python/Streamlit adaptation of the supplied browser-only HTML specification. It implements upload, required-column validation, PII removal, core cleaning, filters, headline KPIs, SLA reconciliation, daily/category/geography/vendor/channel summaries, a basic action panel, health checks, and division matrices. The original specification's large synthetic demo mode, exact burst detection, advanced baseline/hotspot rules, editable interactive cross-filter chips, PDF report, and golden sample assertions are not included in this first version. Those require the sample workbook for verification and/or additional implementation.
