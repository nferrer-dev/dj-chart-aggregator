import re
with open('chronological_archive.md', encoding='utf-8') as f:
    lines = f.readlines()
header = lines[:3]
charts = lines[3:]
seen = set()
deduped = []
for c in charts:
    m = re.search(r'\]\((https?://[^\)]+)\)', c)
    url = m.group(1) if m else c
    if url not in seen:
        seen.add(url)
        deduped.append(c)
with open('chronological_archive.md', 'w', encoding='utf-8') as f:
    f.writelines(header + deduped)
