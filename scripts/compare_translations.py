import sys, os, re
sys.path.insert(0, r'E:\AI-Dubbing')
from fanfic_pipeline.robsten_scraper import get_chapter_sections
from fanfic_pipeline.pdf_parser import FanficPDFParser

sys.stdout.reconfigure(encoding='utf-8')

# Load Gemini translation for Chapter 1
with open(r'E:\AI-Dubbing\work\wide_awake\chapter_01\translated_ru.txt', 'r', encoding='utf-8') as f:
    gemini_ch1 = f.read()

# Load Robsten translation for Chapter 1
robsten_data = get_chapter_sections(1)
robsten_full = "\n\n".join(sec['text'] for sec in robsten_data['sections'])

print("=== LENGTH COMPARISON (Chapter 1) ===")
print(f"Gemini 3.8 Flash: {len(gemini_ch1)} chars")
print(f"Robsten Fan-trans: {len(robsten_full)} chars")

# Let's inspect some specific snippets in both
def find_snippet(text, pattern, max_len=300):
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        start = max(0, m.start() - 20)
        return text[start:start+max_len].strip().replace('\n', ' ')
    return "NOT FOUND"

print("\n--- 1. Bella opening (nightmares / insomnia) ---")
print("[Gemini]: ", gemini_ch1[:250].replace('\n', ' '))
print("[Robsten]:", robsten_full[:250].replace('\n', ' '))

print("\n--- 2. Edward opening (lighter / swearing) ---")
print("[Gemini]: ", find_snippet(gemini_ch1, r'зажигалк|черт|гребан|куда'))
print("[Robsten]:", find_snippet(robsten_full, r'зажигалк|бля|куда'))

print("\n--- 3. Edward & Emmett (banter / smell) ---")
print("[Gemini]: ", find_snippet(gemini_ch1, r'дезодорант|вонюч'))
print("[Robsten]:", find_snippet(robsten_full, r'дезодорант|вонюч'))

print("\n--- 4. Classroom / Crazy Cousin ---")
print("[Gemini]: ", find_snippet(gemini_ch1, r'кузин|шизанут|стол'))
print("[Robsten]:", find_snippet(robsten_full, r'кузин|шизанут|стол'))
