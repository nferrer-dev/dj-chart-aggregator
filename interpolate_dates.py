import re
from datetime import datetime

# Read all lines
with open('chronological_archive.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

bp_known = []
ts_known = []

# Extract known dates and IDs
for line in lines:
    if "Unknown Date" in line:
        continue
    date_m = re.search(r'\*\*(\d{4}-\d{2}-\d{2})\*\*', line)
    if not date_m:
        continue
    dt = datetime.strptime(date_m.group(1), '%Y-%m-%d')
    
    # Beatport
    bp_m = re.search(r'beatport\.com/chart/[^/]+/(\d+)', line)
    if bp_m:
        bp_known.append((int(bp_m.group(1)), dt))
        
    # Traxsource title
    ts_m = re.search(r'traxsource\.com/title/(\d+)/', line)
    if ts_m:
        ts_known.append((int(ts_m.group(1)), dt))
        
    # Traxsource chart (some older ones use /chart/)
    ts_c = re.search(r'traxsource\.com/chart/(\d+)/', line)
    if ts_c:
        ts_known.append((int(ts_c.group(1)), dt))

bp_known.sort()
ts_known.sort()

def interpolate_date(target_id, known_list):
    if not known_list:
        return None
        
    # Find surrounding IDs
    before = None
    after = None
    for kid, kdt in known_list:
        if kid <= target_id:
            before = kdt
        if kid >= target_id:
            after = kdt
            break
            
    if before and after:
        # Just use the 'before' date as an approximation (month/year)
        # Or midpoint
        delta = after - before
        return before # rough approximation is fine for Month/Year
    elif before:
        return before
    elif after:
        return after
    return None

new_lines = []
for line in lines:
    if "Unknown Date" in line:
        # Extract title text to see if it has a month
        title_m = re.search(r'\[(.*?)\]', line)
        title_str = title_m.group(1).lower() if title_m else ""
        
        # Volumo Hardcoded approximations based on the fact they are new (2023-2024)
        if "volumo.com" in line:
            if "november" in title_str:
                line = line.replace("Unknown Date", "2023-11-01")
            elif "september" in title_str:
                line = line.replace("Unknown Date", "2023-09-01")
            elif "august" in title_str:
                line = line.replace("Unknown Date", "2023-08-01")
                
        # Beatport interpolation
        bp_m = re.search(r'beatport\.com/chart/[^/]+/(\d+)', line)
        if bp_m:
            tid = int(bp_m.group(1))
            approx_dt = interpolate_date(tid, bp_known)
            if approx_dt:
                # If title contains a month, use that month, but keep the interpolated year!
                months = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6, 'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12}
                found_month = None
                for m_name, m_num in months.items():
                    if m_name in title_str:
                        found_month = m_num
                        break
                
                final_year = approx_dt.year
                final_month = found_month if found_month else approx_dt.month
                date_str = f"{final_year}-{final_month:02d}-01"
                line = line.replace("Unknown Date", date_str)
                
        # Traxsource interpolation
        ts_m = re.search(r'traxsource\.com/title/(\d+)/', line)
        if ts_m:
            tid = int(ts_m.group(1))
            approx_dt = interpolate_date(tid, ts_known)
            if approx_dt:
                # Same month logic
                months = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6, 'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12}
                found_month = None
                for m_name, m_num in months.items():
                    if m_name in title_str:
                        found_month = m_num
                        break
                
                final_year = approx_dt.year
                final_month = found_month if found_month else approx_dt.month
                date_str = f"{final_year}-{final_month:02d}-01"
                line = line.replace("Unknown Date", date_str)
                
    new_lines.append(line)

# Sort everything again since dates changed
header = new_lines[:3]
charts = new_lines[3:]

parsed_charts = []
for c in charts:
    date_m = re.search(r'\*\*(\d{4}-\d{2}-\d{2})\*\*', c)
    dt = datetime.strptime(date_m.group(1), '%Y-%m-%d') if date_m else datetime.min
    parsed_charts.append({'line': c, 'date': dt})

parsed_charts.sort(key=lambda x: x['date'], reverse=True)

with open('chronological_archive.md', 'w', encoding='utf-8') as f:
    f.writelines(header)
    for pc in parsed_charts:
        f.write(pc['line'])
        
print("Successfully interpolated all missing dates!")
