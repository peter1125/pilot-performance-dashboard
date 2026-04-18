from pathlib import Path
import json
from live_data import load_live_dashboard_payload

payload = load_live_dashboard_payload()
payload['source'] = 'github-pages-notion-sync'
out = Path(__file__).resolve().parent / 'dashboard-data.json'
out.write_text(json.dumps(payload, indent=2))
print(out)
