import json, requests, re
from bs4 import BeautifulSoup
from datetime import datetime

urls = [
    ('Sante', 'https://volumo.com/chart/0CrzFAMepWbh-sante-november-charts'),
    ('Sante', 'https://volumo.com/chart/vITb40Te8cgf-sante-september-heat'),
    ('HNQO', 'https://volumo.com/chart/Hwe5WDrQWGlX-hnqo-august-here-and-there')
]

SCRAPER_API_KEY = "4fecd44a6d961564ae385152f6409654"
new_lines = []

for artist, url in urls:
    try:
        html = requests.get('http://api.scraperapi.com/', params={'api_key': SCRAPER_API_KEY, 'url': url}, timeout=30).text
        soup = BeautifulSoup(html, 'html.parser')
        script = soup.find('script', id='__NEXT_DATA__')
        
        date_str = "Unknown Date"
        title = url.split('-')[-1] # fallback
        
        if script:
            data = json.loads(script.string)
            state = data.get('props', {}).get('pageProps', {}).get('dehydratedState', {})
            queries = state.get('queries', [])
            for q in queries:
                if q.get('queryKey', [''])[0] == 'ChartInfo':
                    chart_data = q.get('state', {}).get('data', {}).get('data', {})
                    title = chart_data.get('title', title)
                    # "createdAt": "2023-11-20T10:15:30.000Z"
                    created_at = chart_data.get('createdAt')
                    if created_at:
                        date_str = created_at.split('T')[0]
                    break
        
        line = f"- **{date_str}** | Volumo | [{title}]({url}) (Curator: {artist})\n"
        new_lines.append((date_str, line))
        print(f"Scraped: {title} | {date_str}")
    except Exception as e:
        print(f"Error on {url}: {e}")

# Inject into archive
with open('chronological_archive.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

header = lines[:3]
charts = lines[3:]

# Just add them and rely on manual sort if needed, or we can parse and sort them all.
parsed_charts = []
for c in charts:
    date_m = re.search(r'\*\*(\d{4}-\d{2}-\d{2})\*\*', c)
    dt = datetime.strptime(date_m.group(1), '%Y-%m-%d') if date_m else datetime.min
    parsed_charts.append({'line': c, 'date': dt})

for date_str, line in new_lines:
    dt = datetime.min
    if date_str != "Unknown Date":
        dt = datetime.strptime(date_str, '%Y-%m-%d')
    parsed_charts.append({'line': line, 'date': dt})

parsed_charts.sort(key=lambda x: x['date'], reverse=True)

with open('chronological_archive.md', 'w', encoding='utf-8') as f:
    f.writelines(header)
    for pc in parsed_charts:
        f.write(pc['line'])

print("Successfully injected missing Volumo charts!")
