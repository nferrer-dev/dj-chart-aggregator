import json, requests, re, time, os
from bs4 import BeautifulSoup
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

SCRAPER_API_KEY = "4fecd44a6d961564ae385152f6409654"

with open('artists.json', 'r', encoding='utf-8') as f:
    artists = json.load(f)

# Load successful artists from existing results to avoid duplicate work
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

print(f"Skipping {len(successful_artists)} already scraped artists.")

write_lock = Lock()

def append_to_results(chart_obj):
    with write_lock:
        with open('trax_results.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(chart_obj) + '\n')

def fetch_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            # Using premium residential proxies to bypass Cloudflare
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

def scrape_traxsource_artist(artist):
    if artist in successful_artists:
        return
        
    print(f"[{artist}] Searching Traxsource...")
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
            print(f"[{artist}] Could not resolve profile URL.")
            # Record it as successful so we don't retry dead artists forever
            append_to_results({'platform': 'Traxsource', 'artist': artist, 'empty': True})
            return
            
        print(f"[{artist}] Resolved to {artist_url}. Paginating charts...")
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
                    append_to_results({
                        'title': title_a.text.strip(),
                        'link': "https://www.traxsource.com" + title_a['href'],
                        'platform': 'Traxsource',
                        'artist': artist,
                        'date_str': date_div.text.strip()
                    })
            
            if not chart_found:
                break
            page += 1
            time.sleep(1) # Polite delay
            
        if not found_any:
            # Save an empty record so we know we finished this artist successfully but found 0 charts
            append_to_results({'platform': 'Traxsource', 'artist': artist, 'empty': True})
            
        print(f"[{artist}] Successfully finished scraping.")
            
    except Exception as e:
        print(f"[{artist}] Error: {e}")

# Extreme low concurrency to bypass Cloudflare bans
with ThreadPoolExecutor(max_workers=3) as executor:
    executor.map(scrape_traxsource_artist, artists)
