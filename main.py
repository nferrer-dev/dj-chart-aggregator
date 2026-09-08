import os
import json
import urllib.parse
import hashlib
from datetime import datetime, timezone
import requests
import time
import re
from feedgen.feed import FeedGenerator

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

def search_beatport_charts(artists):
    """
    Directly scrapes Beatport search using Jina Reader to bypass Cloudflare.
    Extracts chart URLs, thumbnails, and titles via Regex from Jina Markdown.
    """
    organic_results = []
    
    # regex to match: [Title ![Thumbnail](img_url)](chart_url)
    pattern = re.compile(r'\[(.*?)\s*\!\[.*?\]\((.*?)\)\]\((https://www\.beatport\.com/chart/[^\)]+)\)')

    for artist in artists:
        url = f'https://r.jina.ai/https://www.beatport.com/search/charts?q={urllib.parse.quote(artist)}&per_page=50'
        
        # Retry mechanism for rate limits
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    matches = pattern.findall(response.text)
                    for title, img_url, chart_url in matches:
                        # Strict Curator Filter: Reject charts by random bedroom DJs
                        if artist.lower() not in title.lower():
                            continue
                            
                        organic_results.append({
                            'title': title.strip(),
                            'link': chart_url.strip(),
                            'snippet': f"Chart curated by {artist}",
                            'image_url': img_url.strip()
                        })
                    break # Success, move to next artist
                elif response.status_code == 429:
                    print(f"Rate limited on {artist}, waiting 10s...")
                    time.sleep(10)
                else:
                    print(f"Error {response.status_code} for {artist}")
                    break
            except Exception as e:
                print(f"Request failed for {artist}: {e}")
                time.sleep(5)
                
        # 3-second sleep between artists to respect Jina free tier rate limits (20 RPM)
        time.sleep(3)

    return organic_results

def search_google_charts(artists):
    """
    Scrapes Google via Serper.dev for Traxsource and Volumo.
    Uses filter=0 to force Google to show omitted results.
    """
    serper_api_key = os.environ.get("SERPER_API_KEY")
    if not serper_api_key:
        print("Warning: SERPER_API_KEY not found. Skipping Google search.")
        return []

    organic_results = []
    url = "https://google.serper.dev/search"
    headers = {
        'X-API-KEY': serper_api_key,
        'Content-Type': 'application/json'
    }

    for artist in artists:
        query = f'(site:traxsource.com OR site:volumo.com) "{artist}" chart'
        payload = json.dumps({
            "q": query,
            "num": 100,
            "filter": "0" # Forces omitted results
        })
        
        try:
            response = requests.post(url, headers=headers, data=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                results = data.get("organic", [])
                for r in results:
                    organic_results.append({
                        'title': r.get("title", "Untitled Chart"),
                        'link': r.get("link", ""),
                        'snippet': r.get("snippet", ""),
                        'image_url': r.get("imageUrl", "")
                    })
            else:
                print(f"Serper error for {artist}: {response.status_code}")
        except Exception as e:
            print(f"Serper request failed for {artist}: {e}")
            
    return organic_results

def main():
    redis_url = os.environ.get("UPSTASH_REDIS_REST_URL")
    redis_token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    
    if not all([redis_url, redis_token]):
        print("Missing required environment variables (UPSTASH_REDIS).")
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
    
    new_entries_found = False
    
    # Combine Beatport (Jina) and Traxsource/Volumo (Serper)
    valid_items = search_beatport_charts(artists) + search_google_charts(artists)
                    
    if valid_items:
        # Filter against Upstash Redis in one bulk MGET request
        links_to_check = [item['link'] for item in valid_items]
        unseen_links = get_unseen_links(links_to_check, redis_url, redis_token)
        
        new_links_to_mark = []
        for item in valid_items:
            if item['link'] in unseen_links:
                html_desc = ""
                if item.get('image_url'):
                    html_desc += (
                        f'<img src="{item["image_url"]}" '
                        f'style="max-width:100%; border-radius:8px;"/><br/><br/>'
                    )
                
                html_desc += f'<p>{item.get("snippet", "")}</p><br/>'
                
                domain_name = "Beatport"
                if "traxsource.com" in item['link']:
                    domain_name = "Traxsource"
                elif "volumo.com" in item['link']:
                    domain_name = "Volumo"
                
                html_desc += (
                    f'<a href="{item["link"]}" target="_blank">'
                    f'<strong>🔗 View Full Chart on {domain_name}</strong></a>'
                )
                
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

    # Ensure output directory exists
    os.makedirs('output', exist_ok=True)
    
    # Always write the feed, even if no new entries were found today, 
    # to maintain the file existence for GitHub Pages
    if not new_entries_found:
        fe = fg.add_entry()
        fe.id('init-1')
        fe.title('Pipeline Running (No new charts today)')
        fe.link(href='https://github.com')
        fe.description(
            'Your custom pipeline is successfully connected via Jina Reader. '
            'New charts will appear here when they are published.'
        )
        fe.pubDate(datetime.now(timezone.utc))

    fg.rss_file('output/feed.xml')
    print("Feed generated at output/feed.xml")

if __name__ == "__main__":
    main()
