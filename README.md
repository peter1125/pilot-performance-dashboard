# Pilot Performance Dashboard

Permanent public dashboard for the three pilot sleeves.

How it works:
- GitHub Pages serves the static dashboard.
- A GitHub Actions workflow refreshes `dashboard-data.json` from Notion every 5 minutes.
- The browser app loads the latest synced JSON and provides interactive filtering/search/charting.

Files:
- `index.html`, `styles.css`, `app.js` — frontend
- `dashboard-data.json` — latest synced live snapshot for the site
- `live_data.py`, `sync_data.py` — Notion fetch + transformation logic
- `.github/workflows/sync-dashboard.yml` — scheduled sync workflow
