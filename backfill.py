import os
import json
import urllib.parse
import requests
import re
import time
from datetime import datetime
from dateutil import parser as date_parser

# ==========================================
# CONFIGURATION
# ==========================================
# Replace this with your actual Serper API Key!
SERPER_API_KEY = "a39b52fae7f1eeb433042a85db5d73ea8ff98621"

def parse_date(date_string):
    """Attempts to parse a date string. Returns datetime.min if it fails."""
    if not date_string:
        return datetime.min
    try:
        return date_parser.parse(date_string, fuzzy=True)
    except Exception:
        return datetime.min

def get_beatport_charts(artist):
    """Fetch ALL charts for the artist from Beatport via pagination."""
    results = []
    pattern = re.compile(r'\[(.*?)\s*\!\[.*?\]\((.*?)\)\]\((https://www\.beatport\.com/chart/[^\)]+)\)')
    page = 1
    
    while True:
        url = f'https://r.jina.ai/https://www.beatport.com/search/charts?q={urllib.parse.quote(artist)}&per_page=150&page={page}'
        page_results = 0
        
        for attempt in range(3):
            try:
                res = requests.get(url, timeout=30)
                if res.status_code == 200:
                    matches = pattern.findall(res.text)
                    for title, img, link in matches:
                        # Strict Curator Filter: Reject charts by random bedroom DJs
                        if artist.lower() not in title.lower():
                            continue
                            
                        results.append({
                            'title': title.strip(),
                            'link': link.strip(),
                            'platform': 'Beatport',
                            'artist': artist
                        })
                    page_results = len(matches)
                    break
                elif res.status_code == 429:
                    time.sleep(10)
                else:
                    break
            except Exception:
                time.sleep(5)
                
        time.sleep(3) # Jina Rate Limit
        
        if page_results < 150:
            break
        page += 1
        
    return results

def get_serper_charts(artist):
    """Fetch charts from Google (Traxsource & Volumo) via Serper."""
    results = []
    if SERPER_API_KEY == "PASTE_YOUR_SERPER_API_KEY_HERE":
        return results

    url = "https://google.serper.dev/search"
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    
    # Query Traxsource (strictly targeting /title directory)
    try:
        ts_query = f'site:traxsource.com/title "{artist}" chart'
        res_ts = requests.post(url, headers=headers, json={"q": ts_query, "num": 100, "filter": "0"}, timeout=30)
        if res_ts.status_code == 200:
            for r in res_ts.json().get("organic", []):
                title = r.get("title", "")
                # Strict Curator Filter
                if artist.lower() not in title.lower():
                    continue
                # Reject EP/Track releases (must have chart-like keywords)
                keywords = ['chart', 'pick', 'favorite', 'top', 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
                if not any(k in title.lower() for k in keywords):
                    continue
                results.append({
                    'title': title,
                    'link': r.get("link", ""),
                    'platform': 'Traxsource',
                    'artist': artist,
                    'date_str': r.get("date", "")
                })
    except Exception as e:
        pass
        
    # Query Volumo
    try:
        vol_query = f'site:volumo.com "{artist}" chart'
        res_vol = requests.post(url, headers=headers, json={"q": vol_query, "num": 100, "filter": "0"}, timeout=30)
        if res_vol.status_code == 200:
            for r in res_vol.json().get("organic", []):
                title = r.get("title", "")
                # Strict Curator Filter
                if artist.lower() not in title.lower():
                    continue
                # Reject EP/Track releases
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
        pass
        
    return results

def get_beatport_chart_date(url):
    """Visits the actual Beatport chart page to extract the creation date."""
    jina_url = f"https://r.jina.ai/{url}"
    for attempt in range(3):
        try:
            res = requests.get(jina_url, timeout=30)
            if res.status_code == 200:
                # Beatport chart pages usually have "Created: YYYY-MM-DD" or similar
                # We do a fuzzy regex search for dates
                date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, \d{4}', res.text)
                if date_match:
                    return date_match.group(0)
                
                date_match_iso = re.search(r'\d{4}-\d{2}-\d{2}', res.text)
                if date_match_iso:
                    return date_match_iso.group(0)
                
                return ""
            elif res.status_code == 429:
                time.sleep(10)
            else:
                break
        except Exception:
            time.sleep(5)
            
    return ""

def main():
    if not os.path.exists('artists.json'):
        print("artists.json not found! Please create it.")
        return
        
    with open('artists.json', 'r', encoding='utf-8') as f:
        artists = json.load(f)
        
    all_charts = []
    checkpoint_file = 'backfill_checkpoint.json'
    
    # Check if we are resuming from a previous run
    if os.path.exists(checkpoint_file):
        print(f"Found {checkpoint_file}! Resuming from previous state...")
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            all_charts = json.load(f)
    else:
        # STEP 1: Gather all chart URLs
        print("=== STEP 1: GATHERING CHART URLS ===")
        for idx, artist in enumerate(artists):
            print(f"Gathering [{idx+1}/{len(artists)}]: {artist}", flush=True)
            bp_charts = get_beatport_charts(artist)
            sp_charts = get_serper_charts(artist)
            all_charts.extend(bp_charts)
            all_charts.extend(sp_charts)
            
        print(f"\nTotal charts found: {len(all_charts)}")
        # Save initial checkpoint
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(all_charts, f)
    
    # STEP 2: Extract Dates
    print(f"\n=== STEP 2: EXTRACTING DATES (Multithreaded ScraperAPI) ===")
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    SCRAPER_API_KEY = "4fecd44a6d961564ae385152f6409654"
    
    def process_chart(chart, idx, total):
        # Skip if already successfully extracted
        if 'parsed_date_iso' in chart:
            return chart
            
        print(f"Extracting date [{idx+1}/{total}]: {chart['title'][:30]}...", flush=True)
        
        if chart['platform'] == 'Beatport':
            # Clean URL (remove accidentally captured markdown titles)
            clean_url = chart['link'].split(' ')[0].split('"')[0]
            
            payload = {'api_key': SCRAPER_API_KEY, 'url': clean_url}
            for attempt in range(3):
                try:
                    res = requests.get('http://api.scraperapi.com/', params=payload, timeout=60)
                    if res.status_code == 200:
                        date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, \d{4}', res.text)
                        if date_match:
                            chart['date_str'] = date_match.group(0)
                            break
                            
                        date_match_iso = re.search(r'\d{4}-\d{2}-\d{2}', res.text)
                        if date_match_iso:
                            chart['date_str'] = date_match_iso.group(0)
                            break
                        
                        chart['date_str'] = ""
                        break
                    else:
                        time.sleep(2)
                except Exception:
                    time.sleep(2)
                    
        parsed = parse_date(chart.get('date_str', ''))
        chart['parsed_date_iso'] = parsed.isoformat()
        return chart

    # Run multithreaded extraction
    processed_count = 0
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(process_chart, chart, i, len(all_charts)): i for i, chart in enumerate(all_charts)}
        for future in as_completed(futures):
            processed_count += 1
            # Periodically save checkpoint to disk (every 50 charts)
            if processed_count % 50 == 0:
                with open(checkpoint_file, 'w', encoding='utf-8') as f:
                    json.dump(all_charts, f)

    # Final checkpoint save
    with open(checkpoint_file, 'w', encoding='utf-8') as f:
        json.dump(all_charts, f)

    # STEP 3: Sort & Export
    print("\n=== STEP 3: SORTING AND EXPORTING ===")
    
    # Rehydrate dates for sorting
    for chart in all_charts:
        chart['parsed_date'] = datetime.fromisoformat(chart['parsed_date_iso'])
        
    # Sort descending by parsed date
    all_charts.sort(key=lambda x: x['parsed_date'], reverse=True)
    
    with open('chronological_archive.md', 'w', encoding='utf-8') as f:
        f.write("# Master Chronological DJ Chart Archive\n\n")
        f.write("Includes Beatport, Traxsource, and Volumo.\n\n")
        
        for chart in all_charts:
            date_display = chart['parsed_date'].strftime('%Y-%m-%d') if chart['parsed_date'] != datetime.min else "Unknown Date"
            f.write(f"- **{date_display}** | {chart['platform']} | [{chart['title']}]({chart['link']}) (Curator: {chart['artist']})\n")
            
    print("\nDone! Archive saved to chronological_archive.md")
    
    # Cleanup checkpoint
    if os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)

if __name__ == "__main__":
    main()
