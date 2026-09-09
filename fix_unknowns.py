import re
import requests
from datetime import datetime

SCRAPER_API_KEY = "4fecd44a6d961564ae385152f6409654"

with open('chronological_archive.md', encoding='utf-8') as f:
    lines = f.readlines()

header = lines[:3]
charts = lines[3:]
updated_charts = []

month_map = {
    'january': '01', 'jan': '01',
    'february': '02', 'feb': '02',
    'march': '03', 'mar': '03',
    'april': '04', 'apr': '04',
    'may': '05',
    'june': '06', 'jun': '06',
    'july': '07', 'jul': '07',
    'august': '08', 'aug': '08',
    'september': '09', 'sep': '09',
    'october': '10', 'oct': '10',
    'november': '11', 'nov': '11',
    'december': '12', 'dec': '12',
    'summer': '06', 'winter': '12', 'spring': '03', 'autumn': '09', 'fall': '09'
}

def extract_from_string(text):
    # Try Month Year
    m = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec|summer|winter|spring|autumn|fall)\s*(\d{4})', text, re.IGNORECASE)
    if m:
        return f"{m.group(2)}-{month_map[m.group(1).lower()]}-01"
    # Try Year
    m2 = re.search(r'(201\d|202\d)', text)
    if m2:
        return f"{m2.group(1)}-01-01"
    return None

def fetch_html_date(url):
    try:
        res = requests.get('http://api.scraperapi.com/', params={'api_key': SCRAPER_API_KEY, 'url': url}, timeout=30)
        if res.status_code == 200:
            m = extract_from_string(res.text)
            if m: return m
    except:
        pass
    return None

print("Scanning Unknown Dates...")
for c in charts:
    if 'Unknown Date' in c:
        url_match = re.search(r'\]\((https?://[^\s\)]+)', c)
        if not url_match:
            updated_charts.append({'line': c, 'date': datetime.min})
            continue
            
        url = url_match.group(1)
        title_match = re.search(r'\[(.*?)\]\(', c)
        title = title_match.group(1) if title_match else ""
        
        # 1. Try Title
        new_date = extract_from_string(title)
        
        # 2. Try URL
        if not new_date:
            new_date = extract_from_string(url)
            
        # 3. Try HTML
        if not new_date and ('traxsource' in url or 'volumo' in url):
            print(f"Scraping {url}...")
            new_date = fetch_html_date(url)
            
        if new_date:
            print(f"Recovered {new_date} for {title}")
            new_line = c.replace('Unknown Date', new_date)
            parsed = datetime.strptime(new_date, '%Y-%m-%d')
            updated_charts.append({'line': new_line, 'date': parsed})
        else:
            updated_charts.append({'line': c, 'date': datetime.min})
    else:
        date_match = re.search(r'\*\*(\d{4}-\d{2}-\d{2})\*\*', c)
        if date_match:
            parsed = datetime.strptime(date_match.group(1), '%Y-%m-%d')
        else:
            parsed = datetime.min
        updated_charts.append({'line': c, 'date': parsed})

print("Sorting...")
updated_charts.sort(key=lambda x: x['date'], reverse=True)

with open('chronological_archive.md', 'w', encoding='utf-8') as f:
    f.writelines(header)
    for uc in updated_charts:
        f.write(uc['line'])

print("Done!")
