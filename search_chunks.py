import re
import urllib.request
import os

with open('artists.html', 'r', encoding='utf-8') as f:
    html = f.read()

chunks = set(re.findall(r'src="(/_next/static/chunks/[^"]+\.js)"', html))
print(f"Found {len(chunks)} chunks")

for chunk in chunks:
    url = f"https://volumo.com{chunk}"
    filename = url.split('/')[-1]
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as response:
            js = response.read().decode('utf-8')
            if 'search' in js.lower():
                print(f"FOUND 'search' in {filename}")
                with open(filename, 'w', encoding='utf-8') as fw:
                    fw.write(js)
    except Exception as e:
        pass
