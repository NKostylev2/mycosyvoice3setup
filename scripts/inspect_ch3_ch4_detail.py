import sys, os, re
sys.path.insert(0, r'E:\AI-Dubbing')
from fanfic_pipeline.robsten_scraper import fetch_page_text, get_toc
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

for ch in [3, 4]:
    print(f"\n==================== CHAPTER {ch} ====================")
    toc = get_toc()
    entry = [e for e in toc if e['start_num'] <= ch <= e['end_num']][0]
    print(f"Header: {entry['header']} - {entry['title']}")
    for link_idx, l in enumerate(entry['links']):
        html = fetch_page_text(l['url'])
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()
        print(f"\n--- Part {link_idx+1}: {l['part_name']} ({l['url']}) ---")
        print(f"Text length: {len(text)}")
        # Look for headers, banners, b tags
        b_tags = [b.get_text(strip=True) for b in soup.find_all(['b', 'strong', 'h1', 'h2', 'h3']) if len(b.get_text(strip=True)) < 40]
        print(f"Short bold tags: {b_tags[:10]}")
        # Show first 300 chars of text
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        print("First 3 non-empty lines:")
        for line in lines[:3]:
            print("  ", line[:100])
        print("Last 2 non-empty lines:")
        for line in lines[-2:]:
            print("  ", line[:100])
