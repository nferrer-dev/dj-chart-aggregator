import os
import json
import requests
import re
from datetime import datetime
from dateutil import parser as date_parser

SERPER_API_KEY = "a39b52fae7f1eeb433042a85db5d73ea8ff98621"

def parse_date(date_string):
    if not date_string:
        return datetime.min
    try:
        return date_parser.parse(date_string, fuzzy=True)
    except Exception:
        return datetime.min

print("Fetching Traxsource/Volumo...")
artists = json.load(open('artists.json', 'r', encoding='utf-8'))
results = []
for a in artists:
    url = "https://google.serper.dev/search"
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    # Trax
    try:
        res = requests.post(url, headers=headers, json={"q": f'site:traxsource.com/title "{a}" chart', "num": 100, "filter": "0"}).json()
        for r in res.get("organic", []):
            if a.lower() in r.get("title", "").lower():
                results.append({'title': r.get("title", ""), 'link': r.get("link", ""), 'platform': 'Traxsource', 'artist': a, 'date_str': r.get("date", "")})
    except: pass
    # Volumo
    try:
        res = requests.post(url, headers=headers, json={"q": f'site:volumo.com "{a}" chart', "num": 100, "filter": "0"}).json()
        for r in res.get("organic", []):
            if a.lower() in r.get("title", "").lower():
                results.append({'title': r.get("title", ""), 'link': r.get("link", ""), 'platform': 'Volumo', 'artist': a, 'date_str': r.get("date", "")})
    except: pass

print(f"Found {len(results)} new charts!")

# Merge with existing archive
print("Merging with existing archive...")
existing_charts = []
with open('chronological_archive.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    
# Parse existing markdown
pattern = re.compile(r'- \*\*(.*?)\*\* \| (.*?) \| \[(.*?)\]\((.*?)\) \(Curator: (.*?)\)')
for line in lines:
    match = pattern.search(line)
    if match:
        date_str, platform, title, link, artist = match.groups()
        parsed = datetime.min if date_str == "Unknown Date" else datetime.strptime(date_str, "%Y-%m-%d")
        existing_charts.append({'title': title, 'link': link, 'platform': platform, 'artist': artist, 'parsed_date': parsed})

# Parse new dates
for c in results:
    c['parsed_date'] = parse_date(c['date_str'])
    
# Combine and sort
all_charts = existing_charts + results
all_charts.sort(key=lambda x: x['parsed_date'], reverse=True)

with open('chronological_archive.md', 'w', encoding='utf-8') as f:
    f.write("# Master Chronological DJ Chart Archive\n\n")
    f.write("Includes Beatport, Traxsource, and Volumo.\n\n")
    for chart in all_charts:
        date_display = chart['parsed_date'].strftime('%Y-%m-%d') if chart['parsed_date'] != datetime.min else "Unknown Date"
        f.write(f"- **{date_display}** | {chart['platform']} | [{chart['title']}]({chart['link']}) (Curator: {chart['artist']})\n")

print("Done!")
