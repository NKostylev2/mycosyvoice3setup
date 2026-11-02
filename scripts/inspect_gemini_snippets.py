import sys, os, re
sys.path.insert(0, r'E:\AI-Dubbing')

with open(r'E:\AI-Dubbing\work\wide_awake\chapter_01\translated_ru.txt', 'r', encoding='utf-8') as f:
    gemini_ch1 = f.read()

# Search for lighter in gemini
m = re.findall(r'.{0,100}(?:зажигалка|зажигалку|сигарет|прикурить|где я оставил|где, черт).{0,100}', gemini_ch1, re.IGNORECASE)
print(f"Matches in Gemini for lighter/cigarette: {len(m)}")
for match in m:
    print("MATCH:", match.strip().replace('\n', ' '))
