import re
with open('chronological_archive.md', encoding='utf-8') as f:
    lines = f.readlines()
header = lines[:3]
charts = lines[3:]
valid = []
for c in charts:
    if 'Traxsource' in c or 'Volumo' in c:
        m = re.search(r'\[(.*?)\]\(', c)
        title_text = m.group(1).lower() if m else c.lower()
        keywords = ['chart', 'pick', 'favorite', 'top', 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
        if any(k in title_text for k in keywords):
            valid.append(c)
    else:
        valid.append(c)
with open('chronological_archive.md', 'w', encoding='utf-8') as f:
    f.writelines(header + valid)
print('Removed:', len(charts) - len(valid))
