import re
with open('search=Tiger+Stripes.html', 'r', encoding='utf-8') as f:
    html = f.read()
artists = set(re.findall(r'href="/artist/([^"]+)"', html))
print(f"Total unique artists found: {len(artists)}")
print(list(artists)[:10])
