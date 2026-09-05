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


def get_unseen_links(links, redis_url, redis_token):
    if not links:
        return []
    keys = [get_redis_key(link) for link in links]
    res = requests.post(f"{redis_url}/mget", headers={"Authorization": f"Bearer {redis_token}"}, json=keys)
    if res.status_code == 200:
        results = res.json().get("result", [])
        return [link for link, val in zip(links, results) if val is None]
    return links


def mark_seen_bulk(links, redis_url, redis_token):
    if not links:
        return
    pipeline = [["SET", get_redis_key(link), "1", "EX", "2592000"] for link in links]
    requests.post(f"{redis_url}/pipeline", headers={"Authorization": f"Bearer {redis_token}"}, json=pipeline)


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
        query = f'intitle:chart ({artist_query}) (site:beatport.com OR site:traxsource.com OR site:volumo.com)'
        
        payload = json.dumps({
            "q": query,
            "num": 10,
            "tbs": "qdr:y"  # Backfill: look for charts indexed in the last year
        })

        try:
            resp = requests.post(url, headers=headers, data=payload)
            resp.raise_for_status()
            data = resp.json()
            
            valid_items = []
            
            # Serper.dev returns search results in the 'organic' array
            for item in data.get('organic', []):
                raw_link = item.get('link') or ""
                title = item.get('title') or ""
                snippet = item.get('snippet') or ""
                image_url = item.get('imageUrl')
                
                # Strip tracking parameters (like ?srsltid=) to prevent duplicate charts
                link = raw_link.split('?')[0]
                
                # Ensure the link is actually one of our target sites to prevent false positives
                if not any(domain in link for domain in ['beatport.com', 'traxsource.com', 'volumo.com']):
                    continue

                # Strict Check: Ensure the chart was actually CREATED by one of our chunked artists
                # by verifying their name appears in the title tag.
                if not any(a.lower() in title.lower() for a in chunk):
                    continue
                    
                valid_items.append({
                    'link': link,
                    'title': title,
                    'snippet': snippet,
                    'image_url': image_url
                })
                
            if not valid_items:
                continue
                
            # Filter against Upstash Redis in one bulk MGET request
            links_to_check = [item['link'] for item in valid_items]
            unseen_links = get_unseen_links(links_to_check, redis_url, redis_token)
            
            new_links_to_mark = []
            for item in valid_items:
                if item['link'] in unseen_links:
                    html_desc = ""
                    if item['image_url']:
                        html_desc += f'<img src="{item["image_url"]}" style="max-width:100%; border-radius:8px;"/><br/><br/>'
                    
                    html_desc += f'<p>{item["snippet"]}</p><br/>'
                    
                    domain_name = "the Store"
                    if "beatport.com" in item['link']:
                        domain_name = "Beatport"
                    elif "traxsource.com" in item['link']:
                        domain_name = "Traxsource"
                    elif "volumo.com" in item['link']:
                        domain_name = "Volumo"
                    
                    html_desc += f'<a href="{item["link"]}" target="_blank"><strong>🔗 View Full Chart on {domain_name}</strong></a>'
                    
                    fe = fg.add_entry()
                    fe.id(item['link'])
                    fe.title(item['title'])
                    fe.link(href=item['link'])
                    fe.description(html_desc)
                    fe.pubDate(datetime.now(timezone.utc))
                    
                    new_links_to_mark.append(item['link'])
                    new_entries_found = True
                    print(f"Added new chart: {item['title']}")
            
            # Bulk write new links to cache
            if new_links_to_mark:
                mark_seen_bulk(new_links_to_mark, redis_url, redis_token)
                    
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
