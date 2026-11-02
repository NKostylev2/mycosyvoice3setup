import sys, os
sys.path.insert(0, r'E:\AI-Dubbing')
from fanfic_pipeline.robsten_scraper import fetch_page_text
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

# Part 1:
html_p1 = fetch_page_text('http://robsten.ru/publ/nashi_perevody/wide_awake_glava_4_panaceja_iz_arakhisovogo_masla_chast_1/3-1-0-7')
soup1 = BeautifulSoup(html_p1, 'html.parser')
print("Part 1 text length:", len(soup1.get_text()))
print("Part 1 preview:")
print(soup1.get_text()[:600])

# Look for tags with БЕЛЛА / ЭДВАРД in part 1
for tag in soup1.find_all(['b', 'strong', 'p']):
    t = tag.get_text(strip=True).upper()
    if 'БЕЛЛА' in t or 'ЭДВАРД' in t:
        print(f"Tag in Part 1 <{tag.name}>: {t}")

# Part 2:
html_p2 = fetch_page_text('http://robsten.ru/publ/nashi_perevody/wide_awake_glava_4_panaceja_iz_arakhisovogo_masla_chast_2/3-1-0-8')
soup2 = BeautifulSoup(html_p2, 'html.parser')
print("\nPart 2 text length:", len(soup2.get_text()))
print("Part 2 preview:")
print(soup2.get_text()[:600])
for tag in soup2.find_all(['b', 'strong', 'p']):
    t = tag.get_text(strip=True).upper()
    if 'БЕЛЛА' in t or 'ЭДВАРД' in t:
        print(f"Tag in Part 2 <{tag.name}>: {t}")
