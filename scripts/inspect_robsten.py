import requests, sys, re, json
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

url = 'https://robsten.ru/forum/62-40-1'
r = requests.get(url)
soup = BeautifulSoup(r.text, 'html.parser')

target_a = soup.find('a', href=re.compile(r'wide_awake_glava_1'))
parent = target_a.find_parent('td', class_='posttdMessage')

# We can find all lines between 'Содержание:' and 'ДОПОЛНИТЕЛЬНЫЕ МАТЕРИАЛЫ'
# Or parse using regex or BeautifulSoup tags
# Let's inspect the tags inside parent:
chapters = []

# Each chapter line starts with <b>Глава or <b>ЭПИЛОГ or <b>Ауттейк or text 'Глава'
for b_tag in parent.find_all(['b', 'strong']):
    b_text = b_tag.get_text(strip=True)
    if not (re.match(r'^(?:Глава|ЭПИЛОГ|Ауттейк)', b_text, re.I)):
        continue
    
    # Found a header!
    # Let's collect title and all links until next br or next chapter b_tag
    # The title is often in the sibling span or next text
    title_parts = []
    links = []
    
    curr = b_tag.next_sibling
    while curr:
        if getattr(curr, 'name', None) == 'br':
            break
        if getattr(curr, 'name', None) in ['b', 'strong'] and re.match(r'^(?:Глава|ЭПИЛОГ|Ауттейк)', curr.get_text(strip=True), re.I):
            break
        
        if getattr(curr, 'name', None) == 'a' and curr.has_attr('href') and ('publ' in curr['href'] or 'wide_awake' in curr['href']):
            links.append({
                'part_name': curr.get_text(strip=True),
                'url': curr['href']
            })
        elif getattr(curr, 'name', None) == 'span':
            title_parts.append(curr.get_text(strip=True))
        elif isinstance(curr, str):
            st = curr.strip(' \t\n\r-.')
            if st and not st.isdigit() and len(st) > 1:
                title_parts.append(st)
        curr = curr.next_sibling

    title = " ".join(title_parts).strip()
    chapters.append({
        'header': b_text,
        'title': title,
        'links': links
    })

print(f"Parsed {len(chapters)} entries:")
for c in chapters[:15]:
    print(c['header'], "->", c['title'], "->", [l['part_name'] for l in c['links']])

print("...")
for c in chapters[-10:]:
    print(c['header'], "->", c['title'], "->", [l['part_name'] for l in c['links']])
