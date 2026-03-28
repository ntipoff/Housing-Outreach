# Outreach Hub — Housing Complex Search Tool

A Streamlit application for hospice outreach representatives to find, track, and manage low-income housing complex visits across Lewisville, Carrollton, Flower Mound, and Denton, TX.

## Quick Start

```bash
# 1. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # Mac/Linux
.venv\Scripts\activate           # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

The app opens at http://localhost:8501.

---

## File Structure

```
housing_outreach/
├── app.py            # Streamlit UI — all views and routing
├── data.py           # Seed data (replace with live API in production)
├── utils.py          # Business logic: search, visits, contacts, export
├── requirements.txt
└── README.md
```

---

## Features (mapped to User Stories)

| Story | Feature |
|-------|---------|
| 1 | Search complexes by city (multi-select) or natural language |
| 2 | Complex detail view with all fields, map link, flag for follow-up |
| 3 | Data source + last-updated date shown per result |
| 4 | Export search results as CSV or PDF with notes |
| 5 | Log visits with status, surface overdue follow-ups |
| 6 | Add referral contacts, auto-flag hospice eligibility indicators |

---

## Connecting to Real Data (Story 3)

Replace the `COMPLEXES` list in `data.py` with API calls:

- **HUD**: https://hudgis-hud.opendata.arcgis.com/
- **TDHCA**: https://www.tdhca.state.tx.us/housing-search.htm
- **211 Texas**: https://www.211texas.org/

In `utils.py → search_complexes()`, replace the filter with your API request.

---

## Salesforce Integration Notes

Session-state objects (`visits`, `contacts`, `flags`, `notes`) map 1-to-1 to Salesforce objects:

| App | Salesforce |
|-----|-----------|
| `visits` | Activity / Task |
| `contacts` | Contact (linked to Account = complex) |
| `flags` | Campaign Member |
| `notes` | Note / ContentNote |

Use the **Salesforce Python SDK** (`simple-salesforce`) to push/pull these in production.

---

## Non-Functional Notes

- **HIPAA**: No PHI is written to logs. Contact data lives only in `st.session_state` (in-memory). In production, store in HIPAA-compliant Salesforce Healthcare Cloud objects.
- **Role-based access**: Wrap `app.py` startup with an identity check against your IdP or Salesforce session token before rendering any view.
- **Performance**: Search is in-memory (<1 ms). With a live API, add `@st.cache_data(ttl=3600)` to `search_complexes()`.
- **Mobile**: Streamlit's responsive layout works on mobile browsers out of the box.
