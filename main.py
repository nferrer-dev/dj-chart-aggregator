import os
import json
import urllib.parse
import hashlib
from datetime import datetime, timezone
import requests
from feedgen.feed import FeedGenerator

def chunk_list(lst, chunk_size):
    """Yield successive chunk_size-sized chunks from lst."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def get_redis_key(url):
    return hashlib.sha256(url.encode('utf-8')).hexdigest()

def is_seen(url, redis_url, redis_token):
    key = get_redis_key(url)
    res = requests.get(f"{redis_url}/get/{key}", headers={"Authorization": f"Bearer {redis_token}"})
    if res.status_code == 200 and res.json().get("result") is not None:
        return True
    return False

def mark_seen(url, redis_url, redis_token):
    key = get_redis_key(url)
    # Cache for 30 days (2592000 seconds)
    requests.post(f"{redis_url}/set/{key}/1/EX/2592000", headers={"Authorization": f"Bearer {redis_token}"})

def main():
    serper_api_key = os.environ.get("SERPER_API_KEY")
    redis_url = os.environ.get("UPSTASH_REDIS_REST_URL")
    redis_token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    
    if not all([serper_api_key, redis_url, redis_token]):
        print("Missing required environment variables.")
        return

    # Load artists
    if os.path.exists('artists.json'):
        with open('artists.json', 'r', encoding='utf-8') as f:
            artists = json.load(f)
    else:
        print("artists.json not found")
        return

    # Initialize Feed
    fg = FeedGenerator()
    fg.id('https://github.com/nferrer-dev/dj-chart-aggregator')
    fg.title('DJ Chart Aggregator')
    fg.author({'name':'Antigravity Pipeline'})
    fg.link(href='https://github.com/nferrer-dev/dj-chart-aggregator', rel='alternate')
    fg.description('Automated chronological feed of DJ charts from Beatport, Traxsource, and Volumo.')
    fg.language('en')

    # Chunk into 8 to respect typical search query limits
    chunks = chunk_list(artists, 8)
    
    new_entries_found = False

    url = "https://google.serper.dev/search"
    headers = {
        'X-API-KEY': serper_api_key,
        'Content-Type': 'application/json'
    }

    for chunk in chunks:
        # Build the exact query focusing on our target domains
        artist_query = " OR ".join([f'"{a}"' for a in chunk])
        # Force the search index to pull charts from specific domains
        query = f'intitle:chart ({artist_query}) (site:beatport.com OR site:traxsource.com OR site:volumo.com)'
        
        payload = json.dumps({
            "q": query,
            "num": 10,
            "tbs": "qdr:m" # Backfill: look for charts indexed in the last month
        })

        try:
            resp = requests.post(url, headers=headers, data=payload)
            resp.raise_for_status()
            data = resp.json()
            
            # Serper.dev returns search results in the 'organic' array
            for item in data.get('organic', []):
                link = item.get('link')
                title = item.get('title')
                snippet = item.get('snippet', '') # Robust fallback as requested by Design Validation
                
                # Ensure the link is actually one of our target sites to prevent false positives
                if not any(domain in link for domain in ['beatport.com', 'traxsource.com', 'volumo.com']):
                    continue

                # Deduplicate using Upstash Redis
                if not is_seen(link, redis_url, redis_token):
                    fe = fg.add_entry()
                    fe.id(link)
                    fe.title(title)
                    fe.link(href=link)
                    fe.description(snippet)
                    fe.pubDate(datetime.now(timezone.utc))
                    
                    mark_seen(link, redis_url, redis_token)
                    new_entries_found = True
                    print(f"Added new chart: {title}")
                    
        except requests.exceptions.HTTPError as e:
            print(f"Error querying Serper.dev: {e}")
            if e.response is not None:
                print(f"Raw Serper Error Payload: {e.response.text}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    # Ensure output directory exists
    os.makedirs('output', exist_ok=True)
    
    # Always write the feed, even if no new entries were found today, 
    # to maintain the file existence for GitHub Pages
    if not new_entries_found:
        fe = fg.add_entry()
        fe.id('init-1')
        fe.title('DJ Chart Aggregator is Live!')
        fe.link(href='https://github.com/nferrer-dev/dj-chart-aggregator')
        fe.description('Your custom pipeline is successfully connected via Serper.dev. New charts will appear here when they are published.')
        fe.pubDate(datetime.now(timezone.utc))

    fg.rss_file('output/feed.xml')
    print("Feed generated at output/feed.xml")

if __name__ == "__main__":
    main()
