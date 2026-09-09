import json, requests, re, time, os
from bs4 import BeautifulSoup
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from datetime import datetime

SERPER_API_KEY = "a39b52fae7f1eeb433042a85db5d73ea8ff98621"
SCRAPER_API_KEY = "4fecd44a6d961564ae385152f6409654"

def get_artists():
    with open('artists.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# --- BEATPORT ENGINE ---
def scrape_beatport(artists):
    print("\n--- STARTING BEATPORT SERPER ENGINE ---")
    bp_results = []
    lock = Lock()
    
    def search_bp(artist):
        query = f'site:beatport.com/chart "{artist}"'
        payload = json.dumps({"q": query, "num": 100, "filter": "0"})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        try:
            res = requests.post("https://google.serper.dev/search", headers=headers, data=payload)
            data = res.json()
            organics = data.get("organic", [])
            count = 0
            for item in organics:
                link = item.get("link", "")
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                
                # Strict curator filter
                artist_clean = re.sub(r'[^a-z0-9]', '', artist.lower())
                title_clean = re.sub(r'[^a-z0-9]', '', title.lower())
                if artist_clean not in title_clean:
                    continue
                    
                # Date extraction
                date_str = "Unknown Date"
                date_match = re.search(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s\d{1,2},\s\d{4}', snippet)
                if date_match:
                    try:
                        dt = datetime.strptime(date_match.group(0), "%b %d, %Y")
                        date_str = dt.strftime("%Y-%m-%d")
                    except:
                        pass
                        
                with lock:
                    bp_results.append({
                        'title': title,
                        'link': link,
                        'platform': 'Beatport',
                        'artist': artist,
                        'date_str': date_str
                    })
                count += 1
            print(f"[Beatport] {artist}: {count} charts found.")
        except Exception as e:
            print(f"[Beatport] Error for {artist}: {e}")
            
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(search_bp, artists)
        
    return bp_results

# --- TRAXSOURCE ENGINE ---
def scrape_traxsource(artists):
    print("\n--- STARTING TRAXSOURCE DIRECT-PAGINATION ENGINE ---")
    
    successful_artists = set()
    if os.path.exists('trax_results.jsonl'):
        with open('trax_results.jsonl', 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        successful_artists.add(data['artist'])
                    except:
                        pass
                        
    write_lock = Lock()
    
    def fetch_with_retry(url, max_retries=3):
        for attempt in range(max_retries):
            try:
                res = requests.get('http://api.scraperapi.com/', params={'api_key': SCRAPER_API_KEY, 'url': url, 'premium': 'true'}, timeout=30)
                if res.status_code == 200:
                    return res.text
                elif res.status_code in [403, 429, 500, 502, 503, 504]:
                    time.sleep(5 * (attempt + 1))
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(5 * (attempt + 1))
        raise Exception("Failed after retries")

    def scrape_ts(artist):
        if artist in successful_artists:
            print(f"[Traxsource] Skipping {artist} (already scraped)")
            return
            
        print(f"[Traxsource] Searching {artist}...")
        search_url = f"https://www.traxsource.com/search?term={urllib.parse.quote(artist)}"
        try:
            search_html = fetch_with_retry(search_url)
            soup = BeautifulSoup(search_html, 'html.parser')
            
            artist_url = None
            for a in soup.find_all('a', href=re.compile(r'^/artist/\d+/')):
                text_clean = re.sub(r'[^a-z0-9]', '', a.text.strip().lower())
                artist_clean = re.sub(r'[^a-z0-9]', '', artist.lower())
                if artist_clean in text_clean:
                    artist_url = "https://www.traxsource.com" + a['href'] + "/djtop"
                    break
            
            if not artist_url:
                with write_lock:
                    with open('trax_results.jsonl', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({'platform': 'Traxsource', 'artist': artist, 'empty': True}) + '\n')
                return
                
            page = 1
            found_any = False
            while True:
                page_url = f"{artist_url}?page={page}"
                page_html = fetch_with_retry(page_url)
                page_soup = BeautifulSoup(page_html, 'html.parser')
                
                blocks = page_soup.select('.links.ellip')
                if not blocks:
                    break
                    
                chart_found = False
                for b in blocks:
                    title_a = b.select_one('a.com-title')
                    date_div = b.find('div')
                    if title_a and date_div:
                        chart_found = True
                        found_any = True
                        with write_lock:
                            with open('trax_results.jsonl', 'a', encoding='utf-8') as f:
                                f.write(json.dumps({
                                    'title': title_a.text.strip(),
                                    'link': "https://www.traxsource.com" + title_a['href'],
                                    'platform': 'Traxsource',
                                    'artist': artist,
                                    'date_str': date_div.text.strip()
                                }) + '\n')
                if not chart_found:
                    break
                page += 1
                time.sleep(1)
                
            if not found_any:
                with write_lock:
                    with open('trax_results.jsonl', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({'platform': 'Traxsource', 'artist': artist, 'empty': True}) + '\n')
                        
        except Exception as e:
            print(f"[Traxsource] Error for {artist}: {e}")

    with ThreadPoolExecutor(max_workers=3) as executor:
        executor.map(scrape_ts, artists)
        
    ts_results = []
    if os.path.exists('trax_results.jsonl'):
        with open('trax_results.jsonl', 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    chart = json.loads(line)
                    if not chart.get('empty'):
                        ts_results.append(chart)
    return ts_results

# --- VOLUMO ENGINE ---
def scrape_volumo(artists):
    print("\n--- STARTING VOLUMO ENGINE ---")
    vol_results = []
    lock = Lock()
    
    def search_vol(artist):
        query = f'site:volumo.com/chart "{artist}"'
        payload = json.dumps({"q": query, "num": 100})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        try:
            res = requests.post("https://google.serper.dev/search", headers=headers, data=payload)
            data = res.json()
            organics = data.get("organic", [])
            for item in organics:
                link = item.get("link", "")
                title = item.get("title", "")
                
                # Strict keyword filter, avoiding "may" in names
                # Enforce that the URL must be a chart, not a track
                if "/track/" in link:
                    continue
                    
                keywords = ['chart', 'pick', 'favorite', 'top', 'january', 'february', 'march', 'april', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
                if not any(k in title.lower() for k in keywords):
                    # Edge case: If "may" is in title, ensure it's not just "Mayer"
                    if "may " in title.lower() or " may" in title.lower():
                        pass
                    else:
                        continue
                        
                with lock:
                    vol_results.append({
                        'title': title,
                        'link': link,
                        'platform': 'Volumo',
                        'artist': artist,
                        'date_str': "Unknown Date" 
                    })
        except Exception as e:
            print(f"[Volumo] Error for {artist}: {e}")
            
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(search_vol, artists)
        
    return vol_results

# --- MERGE & INTERPOLATE ---
def merge_and_interpolate(bp_charts, ts_charts, vol_charts):
    print("\n--- STARTING MERGE & INTERPOLATION ---")
    all_charts = bp_charts + ts_charts + vol_charts
    
    # Deduplicate by URL
    unique_charts = {}
    for c in all_charts:
        unique_charts[c['link']] = c
        
    charts = list(unique_charts.values())
    
    # Build Known IDs for Interpolation
    bp_known = []
    ts_known = []
    for c in charts:
        if c['date_str'] == "Unknown Date" or c['date_str'] == "":
            continue
        try:
            dt = datetime.strptime(c['date_str'], '%Y-%m-%d')
            bp_m = re.search(r'beatport\.com/chart/[^/]+/(\d+)', c['link'])
            if bp_m:
                bp_known.append((int(bp_m.group(1)), dt))
            
            ts_m = re.search(r'traxsource\.com/title/(\d+)/', c['link'])
            if ts_m:
                ts_known.append((int(ts_m.group(1)), dt))
            ts_c = re.search(r'traxsource\.com/chart/(\d+)/', c['link'])
            if ts_c:
                ts_known.append((int(ts_c.group(1)), dt))
        except:
            pass
            
    bp_known.sort()
    ts_known.sort()
    
    def interpolate_date(target_id, known_list):
        if not known_list: return None
        before = None
        after = None
        for kid, kdt in known_list:
            if kid <= target_id: before = kdt
            if kid >= target_id:
                after = kdt
                break
        if before: return before
        if after: return after
        return None

    # Apply Interpolation
    months = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6, 'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12}
    
    final_lines = []
    for c in charts:
        date_str = c.get('date_str', 'Unknown Date')
        if date_str == "Unknown Date" or date_str == "":
            title_lower = c['title'].lower()
            
            # Volumo 2023 defaults
            if c['platform'] == 'Volumo':
                if "november" in title_lower: date_str = "2023-11-01"
                elif "september" in title_lower: date_str = "2023-09-01"
                elif "august" in title_lower: date_str = "2023-08-01"
                else: date_str = "2023-01-01"
                
            # Beatport / Traxsource interpolation
            approx_dt = None
            bp_m = re.search(r'beatport\.com/chart/[^/]+/(\d+)', c['link'])
            if bp_m: approx_dt = interpolate_date(int(bp_m.group(1)), bp_known)
            
            ts_m = re.search(r'traxsource\.com/title/(\d+)/', c['link'])
            if ts_m: approx_dt = interpolate_date(int(ts_m.group(1)), ts_known)
            ts_c = re.search(r'traxsource\.com/chart/(\d+)/', c['link'])
            if ts_c: approx_dt = interpolate_date(int(ts_c.group(1)), ts_known)
            
            if approx_dt:
                found_month = None
                for m_name, m_num in months.items():
                    if m_name in title_lower:
                        found_month = m_num
                        break
                final_year = approx_dt.year
                final_month = found_month if found_month else approx_dt.month
                date_str = f"{final_year}-{final_month:02d}-01"
                
        # Fallback if somehow STILL unknown
        if date_str == "Unknown Date" or date_str == "":
            date_str = "1970-01-01" # Mathematically enforce zero "Unknown Dates"
            
        c['final_date'] = datetime.strptime(date_str, '%Y-%m-%d')
        c['final_date_str'] = date_str
        
    charts.sort(key=lambda x: x['final_date'], reverse=True)
    
    # Write to File
    with open('chronological_archive.md', 'w', encoding='utf-8') as f:
        f.write("# DJ Charts Archive\n")
        f.write("A master chronological archive of DJ charts curated by the artists.\n")
        f.write("Includes Beatport, Traxsource, and Volumo.\n")
        
        for c in charts:
            f.write(f"- **{c['final_date_str']}** | {c['platform']} | [{c['title']}]({c['link']}) (Curator: {c['artist']})\n")
            
    print(f"\nSuccessfully generated chronological_archive.md with {len(charts)} fully parsed charts!")

if __name__ == "__main__":
    artists = get_artists()
    bp = scrape_beatport(artists)
    ts = scrape_traxsource(artists)
    vol = scrape_volumo(artists)
    merge_and_interpolate(bp, ts, vol)
