import requests
import json
url = "https://api.apify.com/v2/store"
res = requests.get(url)
if res.status_code == 200:
    data = res.json()
    actors = data.get('data', {}).get('items', [])
    cf_actors = [a for a in actors if 'bypass' in a.get('title', '').lower() or 'cloudflare' in a.get('title', '').lower() or 'cloudflare' in a.get('name', '').lower()]
    for a in cf_actors[:15]:
        print(f"Name: {a['name']}")
else:
    print(f"Failed to fetch store: {res.status_code}")
