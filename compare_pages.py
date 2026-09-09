import re

def get_charts(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        html = f.read()
    return set(re.findall(r'href="(/chart/[^"]+)"', html))

p1 = get_charts('charts.html')
p2 = get_charts('charts_page_2.html')

print(f"Page 1: {len(p1)} charts")
print(f"Page 2: {len(p2)} charts")

intersection = p1.intersection(p2)
print(f"Intersection: {len(intersection)}")
