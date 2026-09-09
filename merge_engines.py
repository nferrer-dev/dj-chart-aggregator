import json, re
from datetime import datetime

trax_charts = []
with open('trax_results.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            chart = json.loads(line)
            if not chart.get('empty'):
                trax_charts.append(chart)

with open('vol_results.json', 'r', encoding='utf-8') as f:
    vol_charts = json.load(f)

new_charts = trax_charts + vol_charts

with open('chronological_archive.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

header = lines[:3]
existing_charts = lines[3:]
seen_urls = set()
parsed_charts = []

# Parse existing charts
for c in existing_charts:
    url_m = re.search(r'\]\((https?://[^\s\)]+)', c)
    if url_m:
        url = url_m.group(1)
        seen_urls.add(url)
    
    date_m = re.search(r'\*\*(\d{4}-\d{2}-\d{2})\*\*', c)
    dt = datetime.strptime(date_m.group(1), '%Y-%m-%d') if date_m else datetime.min
    parsed_charts.append({'line': c, 'date': dt})

added = 0
for c in new_charts:
    if c['link'] not in seen_urls:
        seen_urls.add(c['link'])
        added += 1
        
        # Try to parse date
        dt = datetime.min
        if c['date_str']:
            try:
                # Format: 2018-04-11 or similar
                dt_m = re.search(r'(\d{4}-\d{2}-\d{2})', c['date_str'])
                if dt_m:
                    dt = datetime.strptime(dt_m.group(1), '%Y-%m-%d')
                else:
                    # Traxsource sometimes has format "11 Apr 2018" or "April 2018"
                    # But the /djtop scrape extracted "2018-04-11" natively from the div!
                    pass
            except:
                pass
                
        date_display = dt.strftime('%Y-%m-%d') if dt != datetime.min else "Unknown Date"
        line = f"- **{date_display}** | {c['platform']} | [{c['title']}]({c['link']}) (Curator: {c['artist']})\n"
        
        # If it's still Unknown, check if the old fix_unknown logic can recover it from the title
        if dt == datetime.min:
            m = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec|summer|winter|spring|autumn|fall)\s*(\d{4})', c['title'], re.IGNORECASE)
            if m:
                month_map = {'january': '01', 'jan': '01', 'february': '02', 'feb': '02', 'march': '03', 'mar': '03', 'april': '04', 'apr': '04', 'may': '05', 'june': '06', 'jun': '06', 'july': '07', 'jul': '07', 'august': '08', 'aug': '08', 'september': '09', 'sep': '09', 'october': '10', 'oct': '10', 'november': '11', 'nov': '11', 'december': '12', 'dec': '12', 'summer': '06', 'winter': '12', 'spring': '03', 'autumn': '09', 'fall': '09'}
                rec_date = f"{m.group(2)}-{month_map[m.group(1).lower()]}-01"
                dt = datetime.strptime(rec_date, '%Y-%m-%d')
                line = line.replace('Unknown Date', rec_date)
        
        parsed_charts.append({'line': line, 'date': dt})

parsed_charts.sort(key=lambda x: x['date'], reverse=True)

# Final dedup just in case
final_lines = []
seen_urls = set()
for pc in parsed_charts:
    url_m = re.search(r'\]\((https?://[^\s\)]+)', pc['line'])
    if url_m:
        url = url_m.group(1)
        if url not in seen_urls:
            seen_urls.add(url)
            final_lines.append(pc['line'])
    else:
        final_lines.append(pc['line'])

with open('chronological_archive.md', 'w', encoding='utf-8') as f:
    f.writelines(header)
    for fl in final_lines:
        f.write(fl)
print(f"Added {added} new unique charts to the archive!")
