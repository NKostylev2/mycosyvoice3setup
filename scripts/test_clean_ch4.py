import sys, os, re
sys.path.insert(0, r'E:\AI-Dubbing')
from fanfic_pipeline.robsten_scraper import fetch_page_text, get_toc
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

def test_clean_part(url, default_pov='bella'):
    html = fetch_page_text(url)
    soup = BeautifulSoup(html, 'html.parser')
    for br in soup.find_all('br'):
        br.replace_with('\n')

    for tag in soup.find_all(['b', 'strong', 'p', 'div', 'span']):
        t = tag.get_text(strip=True).upper()
        if t in ["БЕЛЛА", "BELLA", "БЕЛЛА POV", "БЕЛЛА POV."]:
            tag.replace_with("\n===POV:BELLA===\n")
        elif t in ["ЭДВАРД", "EDWARD", "ЭДВАРД POV", "ЭДВАРД POV."]:
            tag.replace_with("\n===POV:EDWARD===\n")

    text = soup.get_text()
    for stopper in ["Источник :", "Источник:", "Переводчики:", "Перевод:", "Скачать фанфик"]:
        if stopper in text:
            text = text.split(stopper)[0]

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    cleaned_lines = []
    for l in lines:
        # Check if line is title banner like '4. Peanut Butter Panaceas - Панацея Из Арахисового Масла'
        if re.match(r'^\d+\.?\s*[A-Za-z\s]+[-–—/]\s*[\w\s]+', l) and len(l) < 100:
            continue
        if re.match(r'^\d+\.?\s*[\w\s]+[-–—/]\s*[A-Za-z\s]+', l) and len(l) < 100:
            continue
        cleaned_lines.append(l)

    return "\n".join(cleaned_lines)

print("Chapter 4 Part 1 cleaned:")
cleaned_ch4_p1 = test_clean_part('http://robsten.ru/publ/nashi_perevody/wide_awake_glava_4_panaceja_iz_arakhisovogo_masla_chast_1/3-1-0-7')
print(cleaned_ch4_p1[:300])

print("\nChapter 4 Part 2 cleaned:")
cleaned_ch4_p2 = test_clean_part('http://robsten.ru/publ/nashi_perevody/wide_awake_glava_4_panaceja_iz_arakhisovogo_masla_chast_2/3-1-0-8')
print(cleaned_ch4_p2[:300])
