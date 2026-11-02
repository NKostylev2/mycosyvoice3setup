import os
import re
from typing import List, Dict, Tuple
import pypdf

from fanfic_pipeline.config import PDF_PATH

class FanficPDFParser:
    def __init__(self, pdf_path: str = PDF_PATH):
        self.pdf_path = pdf_path
        self.reader = pypdf.PdfReader(pdf_path)
        self.total_pages = len(self.reader.pages)
        self.toc = self._parse_toc()

    def _parse_toc(self) -> List[Dict]:
        """
        Parses the table of contents from the PDF (pages 4 to 6, 0-indexed 3 to 5).
        Returns a list of dicts: [{'chapter_num': 1, 'title': 'Gingerbread Zombies', 'start_page': 7, 'end_page': 19}, ...]
        """
        entries = []
        for p in range(3, 6):
            text = self.reader.pages[p].extract_text()
            for line in text.splitlines():
                line = line.strip()
                m = re.match(r'^Chapter\s+(\d+)[\.:\s]+(.*?)\s*[\.\s]{5,}\s*(\d+)$', line, re.IGNORECASE)
                if m:
                    ch_num = int(m.group(1))
                    ch_name = m.group(2).strip()
                    start_page = int(m.group(3))
                    entries.append({
                        'chapter_num': ch_num,
                        'title': ch_name,
                        'full_title': f"Chapter {ch_num}. {ch_name}",
                        'start_page': start_page,
                    })

        # Calculate end_page for each chapter
        for i in range(len(entries)):
            if i + 1 < len(entries):
                entries[i]['end_page'] = entries[i + 1]['start_page'] - 1
            else:
                entries[i]['end_page'] = self.total_pages

        return entries

    def get_chapter_info(self, chapter_num: int) -> Dict:
        for ch in self.toc:
            if ch['chapter_num'] == chapter_num:
                return ch
        raise ValueError(f"Chapter {chapter_num} not found in TOC.")

    def extract_chapter_text(self, chapter_num: int) -> Tuple[Dict, str]:
        info = self.get_chapter_info(chapter_num)
        start_idx = info['start_page'] - 1
        end_idx = info['end_page'] - 1

        raw_pages = []
        for p in range(start_idx, end_idx + 1):
            if p >= self.total_pages:
                break
            raw_pages.append(self.reader.pages[p].extract_text())

        cleaned_text = self._clean_chapter_pages(raw_pages, info['chapter_num'])
        return info, cleaned_text

    def _clean_chapter_pages(self, pages: List[str], chapter_num: int) -> str:
        paragraphs = []
        current_p_lines = []

        for p_idx, page_str in enumerate(pages):
            lines = page_str.splitlines()
            cleaned_lines = []
            
            # Filter out page numbers and repeated title headers
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    cleaned_lines.append("")
                    continue
                # Page number
                if re.match(r'^\d+$', stripped):
                    continue
                # Heading repetition
                if stripped.lower() == "wide awake":
                    continue
                if re.match(r'^chapter\s+' + str(chapter_num) + r'[\.:\s]', stripped, re.IGNORECASE):
                    continue
                cleaned_lines.append(stripped)

            # Strip leading and trailing empty lines of the page
            while cleaned_lines and not cleaned_lines[0]:
                cleaned_lines.pop(0)
            while cleaned_lines and not cleaned_lines[-1]:
                cleaned_lines.pop()

            # Process lines into paragraphs
            for line in cleaned_lines:
                if not line:
                    if current_p_lines:
                        p_text = " ".join(current_p_lines).strip()
                        if p_text:
                            paragraphs.append(p_text)
                        current_p_lines = []
                else:
                    # Check for hyphenation at the end of word
                    if current_p_lines and current_p_lines[-1].endswith("-") and not current_p_lines[-1].endswith(" -"):
                        current_p_lines[-1] = current_p_lines[-1][:-1] + line
                    else:
                        current_p_lines.append(line)

        if current_p_lines:
            p_text = " ".join(current_p_lines).strip()
            if p_text:
                paragraphs.append(p_text)

        # Merge accidental paragraph breaks across pages
        # If paragraph i ends without terminal punctuation, and paragraph i+1 starts with lowercase or continuation
        merged_paragraphs = []
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            if merged_paragraphs:
                prev = merged_paragraphs[-1]
                # If previous doesn't end with sentence terminator (.?!") and next starts with lowercase
                # or previous ends with comma/dash/conjunction
                if not re.search(r'[\.\?!]["\']?$', prev) or re.match(r'^[a-z]', p):
                    merged_paragraphs[-1] = prev + " " + p
                    continue
            merged_paragraphs.append(p)

        full_text = "\n\n".join(merged_paragraphs)
        
        # Normalize smart quotes / dashes
        full_text = full_text.replace("’", "'").replace("‘", "'")
        full_text = full_text.replace("“", '"').replace("”", '"')
        full_text = full_text.replace("—", " — ").replace("–", " - ")
        # Clean extra spaces
        full_text = re.sub(r'[ \t]+', ' ', full_text)
        full_text = re.sub(r'\n{3,}', '\n\n', full_text)

        return full_text.strip()

if __name__ == "__main__":
    parser = FanficPDFParser()
    print(f"Total chapters: {len(parser.toc)}")
    ch1_info, ch1_text = parser.extract_chapter_text(1)
    print(f"Chapter 1: {ch1_info['title']} (pages {ch1_info['start_page']}-{ch1_info['end_page']})")
    print(f"Length in chars: {len(ch1_text)}")
    print(f"Paragraphs: {len(ch1_text.splitlines())}")
    print("\n--- First 3 paragraphs ---")
    for p in ch1_text.split("\n\n")[:3]:
        print("P:", p)
        print()
