"""
Robsten.ru scraper and chapter parser for Wide Awake translation.
Extracts clean POV sections (Bella vs. Edward) from human-translated text.
"""

import os
import re
import json
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from fanfic_pipeline.censor import censor_text

logger = logging.getLogger(__name__)

FORUM_TOC_URL = "https://robsten.ru/forum/62-40-1"
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache", "robsten")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def get_toc(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Fetch and return the table of contents of all chapters from robsten.ru."""
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, "toc.json")
    if os.path.exists(cache_file) and not force_refresh:
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    logger.info(f"Fetching TOC from {FORUM_TOC_URL}...")
    r = requests.get(FORUM_TOC_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    target_a = soup.find("a", href=re.compile(r"wide_awake_glava_1"))
    if not target_a:
        raise ValueError("Could not find Wide Awake TOC in forum post")
    parent = target_a.find_parent("td", class_="posttdMessage")

    chapters = []
    for b_tag in parent.find_all(["b", "strong"]):
        b_text = b_tag.get_text(strip=True)
        if not re.match(r"^(?:Глава|ЭПИЛОГ|Ауттейк)", b_text, re.I):
            continue

        title_parts = []
        links = []
        curr = b_tag.next_sibling
        while curr:
            if getattr(curr, "name", None) == "br":
                break
            if getattr(curr, "name", None) in ["b", "strong"] and re.match(r"^(?:Глава|ЭПИЛОГ|Ауттейк)", curr.get_text(strip=True), re.I):
                break

            if getattr(curr, "name", None) == "a" and curr.has_attr("href") and ("publ" in curr["href"] or "wide_awake" in curr["href"]):
                links.append({
                    "part_name": curr.get_text(strip=True),
                    "url": curr["href"]
                })
            elif getattr(curr, "name", None) == "span":
                title_parts.append(curr.get_text(strip=True))
            elif isinstance(curr, str):
                st = curr.strip(" \t\n\r-.")
                if st and not st.isdigit() and len(st) > 1:
                    title_parts.append(st)
            curr = curr.next_sibling

        title = " ".join(title_parts).strip()
        # Clean title
        title = re.sub(r"\s+", " ", title)

        # Extract chapter number(s)
        m = re.search(r"(\d+)(?:\s*[-–—]\s*(\d+))?", b_text)
        if m:
            start_num = int(m.group(1))
            end_num = int(m.group(2)) if m.group(2) else start_num
        elif "ЭПИЛОГ" in b_text.upper():
            start_num, end_num = 999, 999
        elif "Ауттейк" in b_text:
            m_a = re.search(r"(\d+)", b_text)
            start_num = 1000 + (int(m_a.group(1)) if m_a else 1)
            end_num = start_num
        else:
            start_num, end_num = 0, 0

        chapters.append({
            "header": b_text,
            "start_num": start_num,
            "end_num": end_num,
            "title": title,
            "links": links
        })

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(chapters, f, ensure_ascii=False, indent=2)

    logger.info(f"Loaded TOC with {len(chapters)} entries.")
    return chapters


def fetch_page_text(url: str, force_refresh: bool = False) -> str:
    """Fetch a single robsten publ page and return raw HTML from article tag."""
    ensure_cache_dir()
    slug = url.strip("/").split("/")[-2] if "/" in url else "page"
    part_id = url.strip("/").split("/")[-1]
    cache_file = os.path.join(CACHE_DIR, f"{slug}_{part_id}.html")

    if os.path.exists(cache_file) and not force_refresh:
        with open(cache_file, "r", encoding="utf-8") as f:
            return f.read()

    logger.info(f"Downloading {url}...")
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    art = soup.find("article")
    if not art:
        content_div = soup.find("div", id="content")
        art = content_div if content_div else soup

    html_content = str(art)
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    return html_content


def clean_and_split_sections(html_snippets: List[str], default_pov: str = "bella") -> List[Dict[str, str]]:
    """
    Parse one or more HTML snippets (parts of a chapter) into ordered POV sections.
    Detects markers like <b>БЕЛЛА</b>, <b>ЭДВАРД</b>, banners, etc.
    """
    sections: List[Dict[str, str]] = []
    current_pov = default_pov
    current_paragraphs: List[str] = []

    for html in html_snippets:
        soup = BeautifulSoup(html, "html.parser")

        # Replace <br> with newlines
        for br in soup.find_all("br"):
            br.replace_with("\n")

        # Normalize POV marker tags
        for tag in soup.find_all(["b", "strong", "p", "div", "span"]):
            # Only consider short tags
            t = tag.get_text(strip=True).upper()
            if t in ["БЕЛЛА", "BELLA", "БЕЛЛА POV", "БЕЛЛА POV."]:
                tag.replace_with("\n===POV:BELLA===\n")
            elif t in ["ЭДВАРД", "EDWARD", "ЭДВАРД POV", "ЭДВАРД POV."]:
                tag.replace_with("\n===POV:EDWARD===\n")

        text = soup.get_text()

        # Remove trailing sources and footers
        for stopper in ["Источник :", "Источник:", "Переводчики:", "Перевод:", "Скачать фанфик"]:
            if stopper in text:
                text = text.split(stopper)[0]

        # Clean noise lines
        lines = text.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove title banners or headers like "Chapter 5. Maniacal Mints / МАНИАКАЛЬНАЯ МЯТА"
            if len(line) < 130:
                if re.match(r"^(?:Chapter|Глава)?\s*\d*\.?\s*[-A-Za-z\s–—]+[-–—/]\s*[-А-Яа-яЁёA-Za-z\s–—]+$", line, re.I):
                    continue
                if re.match(r"^(?:Chapter|Глава)?\s*\d*\.?\s*[-А-Яа-яЁёA-Za-z\s–—]+[-–—/]\s*[-A-Za-z\s–—]+$", line, re.I):
                    continue
                if re.match(r"^[-A-Za-z\s–—]+[-–—/]\s*[-А-Яа-яЁёA-Za-z\s–—]+$", line):
                    continue
                if re.match(r"^[-А-Яа-яЁёA-Za-z\s–—]+[-–—/]\s*[-A-Za-z\s–—]+$", line):
                    continue
                if re.match(r"^(?:ГЛАВА|Глава|CHAPTER|Chapter)\s*\d+(\.\d+)?$", line, re.I):
                    continue
                if line.startswith("Wide Awake."):
                    continue

            if line == "===POV:BELLA===":
                if current_paragraphs:
                    sec_text = "\n\n".join(current_paragraphs).strip()
                    if sec_text:
                        sections.append({"pov": current_pov, "text": sec_text})
                    current_paragraphs = []
                current_pov = "bella"
            elif line == "===POV:EDWARD===":
                if current_paragraphs:
                    sec_text = "\n\n".join(current_paragraphs).strip()
                    if sec_text:
                        sections.append({"pov": current_pov, "text": sec_text})
                    current_paragraphs = []
                current_pov = "edward"
            else:
                # Normal paragraph text
                current_paragraphs.append(line)

    if current_paragraphs:
        sec_text = "\n\n".join(current_paragraphs).strip()
        if sec_text:
            sections.append({"pov": current_pov, "text": sec_text})

    # Consolidate any consecutive sections with the same POV
    merged_sections: List[Dict[str, str]] = []
    for sec in sections:
        if merged_sections and merged_sections[-1]["pov"] == sec["pov"]:
            merged_sections[-1]["text"] += "\n\n" + sec["text"]
        else:
            merged_sections.append(sec)

    return merged_sections


def get_chapter_sections(chapter_num: int, force_refresh: bool = False, apply_censor: bool = True) -> Dict[str, Any]:
    """
    Retrieve all POV sections for a given chapter number.
    Returns: {
        'chapter_num': int,
        'title': str,
        'header': str,
        'sections': [{'pov': 'bella'|'edward', 'text': str, 'char_count': int}]
    }
    """
    toc = get_toc(force_refresh=force_refresh)
    target_entry = None
    for entry in toc:
        if entry["start_num"] <= chapter_num <= entry["end_num"]:
            target_entry = entry
            break

    if not target_entry:
        raise ValueError(f"Chapter {chapter_num} not found in Robsten TOC")

    html_snippets = []
    for link in target_entry["links"]:
        html = fetch_page_text(link["url"], force_refresh=force_refresh)
        html_snippets.append(html)

    # By default, chapters start with Bella unless specified otherwise (like Chapter 18 which is Edward POV)
    default_pov = "edward" if "Эдвард POV" in target_entry["title"] or "Эдвард POV" in target_entry["header"] else "bella"
    sections = clean_and_split_sections(html_snippets, default_pov=default_pov)

    for sec in sections:
        if apply_censor:
            cleaned_text, reps = censor_text(sec["text"])
            sec["text"] = cleaned_text
            sec["censor_reps"] = reps
        sec["char_count"] = len(sec["text"])

    return {
        "chapter_num": chapter_num,
        "title": target_entry["title"],
        "header": target_entry["header"],
        "sections": sections
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    for ch in [1, 2]:
        data = get_chapter_sections(ch)
        print(f"\n==========================================")
        print(f"Chapter {ch}: {data['header']} - {data['title']}")
        print(f"Sections count: {len(data['sections'])}")
        for i, s in enumerate(data['sections']):
            print(f"  Section {i+1} [{s['pov']}]: {s['char_count']} chars")
            print(f"    Starts: {repr(s['text'][:60])}")
            print(f"    Ends:   {repr(s['text'][-60:])}")
