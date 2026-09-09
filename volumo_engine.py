import json, requests

SERPER_API_KEY = "a39b52fae7f1eeb433042a85db5d73ea8ff98621"

with open('artists.json', 'r', encoding='utf-8') as f:
    artists = json.load(f)

results = []
url = "https://google.serper.dev/search"
headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}

for artist in artists:
    print(f"[{artist}] Searching Volumo via Serper...")
    try:
        vol_query = f'site:volumo.com "{artist}" chart'
        res_vol = requests.post(url, headers=headers, json={"q": vol_query, "num": 100, "filter": "0"}, timeout=30)
        if res_vol.status_code == 200:
            for r in res_vol.json().get("organic", []):
                title = r.get("title", "")
                if artist.lower() not in title.lower():
                    continue
                keywords = ['chart', 'pick', 'favorite', 'top', 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
                if not any(k in title.lower() for k in keywords):
                    continue
                results.append({
                    'title': title,
                    'link': r.get("link", ""),
                    'platform': 'Volumo',
                    'artist': artist,
                    'date_str': r.get("date", "")
                })
    except Exception as e:
        print(f"[{artist}] Error: {e}")

with open('vol_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f)
print(f"Total Volumo charts scraped: {len(results)}")
