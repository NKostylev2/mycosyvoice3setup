import sys, os, re, json
sys.path.insert(0, r'E:\AI-Dubbing')

from fanfic_pipeline.robsten_scraper import get_chapter_sections
from fanfic_pipeline.pdf_parser import FanficPDFParser

# 1. Load Chapter 1
with open(r'E:\AI-Dubbing\work\wide_awake\chapter_01\translated_ru.txt', 'r', encoding='utf-8') as f:
    gemini_ch1_text = f.read()

robsten_ch1 = get_chapter_sections(1)
parser = FanficPDFParser()
_, en_ch1_text = parser.extract_chapter_text(1)

# 2. Load Chapter 2
with open(r'E:\AI-Dubbing\work\wide_awake\chapter_02\translated_ru.txt', 'r', encoding='utf-8') as f:
    gemini_ch2_text = f.read()

robsten_ch2 = get_chapter_sections(2)
_, en_ch2_text = parser.extract_chapter_text(2)

def extract_side_by_side():
    # Let's find specific parallel scenes in Chapter 1
    # Scene 1: Bella opening (fear, bedroom, Esme, cookies)
    # Scene 2: Edward opening (lighter, cursing, bedroom)
    # Scene 3: Edward & Emmett & Carlisle (deodorant, dad K)
    # Scene 4: Class sleep / Edward reaction
    # Scene 5: Chapter 2 Cafeteria / Edward Cullen exchange
    
    comparisons = []
    
    # Scene 1
    en_s1 = "I hated this room with the deeply-rooted, fiery passion of a million hells. I wasn't trying to be melodramatic, truly."
    gem_s1 = gemini_ch1_text.split('\n\n')[0]
    rob_s1 = robsten_ch1['sections'][0]['text'].split('\n\n')[0]
    comparisons.append({
        "scene": "1. Начало главы 1 (Белла: бессонница и комната)",
        "en": en_s1,
        "gemini": gem_s1,
        "robsten": rob_s1,
        "notes": "У Gemini: буквализм 'огненной страстью миллиона адов' (fiery passion of a million hells), 'склонной к излишней драме'. У Robsten: живое 'со всей силой своей яростной, глубоко запрятанной, ненависти миллионы чертовы раз' и 'быть такой мелодраматичной'."
    })

    # Scene 2: Edward opening
    en_s2 = "Where the fuck did I put that lighter?! I circled my bedroom for the third time, fingers raking through my hair, in complete aggravation. I'd just woken up from twenty minutes of so-called sleep—special fucking sleep—and I really needed this damn cigarette."
    # Find in gemini
    gem_s2 = ""
    for p in gemini_ch1_text.split('\n\n'):
        if 'зажигалк' in p.lower() or 'сигарет' in p.lower():
            gem_s2 = p
            break
    rob_s2 = robsten_ch1['sections'][1]['text'].split('\n\n')[0]
    comparisons.append({
        "scene": "2. Вход Эдварда в главе 1 (Мат, сигареты, ломка от недосыпа)",
        "en": en_s2,
        "gemini": gem_s2,
        "robsten": rob_s2,
        "notes": "У Gemini: сглаженный или стерильный перевод ('где, черт возьми, зажигалка'), тогда как у Robsten сохранен аутентичный нервный мат подросткового Эдварда: 'Куда, бля, я положил эту чертову зажигалку?! ... особого гребаного сна'."
    })

    # Scene 3: Emmett & Carlisle
    en_s3 = "'Holy shit, Em. You're a fucking skunk. Go take a shower before Carlisle gives a lecture on the benefits of deodorant,' I snapped, shoving his arm off in disgust."
    gem_s3 = ""
    for p in gemini_ch1_text.split('\n\n'):
        if 'дезодорант' in p.lower():
            gem_s3 = p
            break
    rob_s3 = ""
    for p in robsten_ch1['sections'][1]['text'].split('\n\n'):
        if 'дезодорант' in p.lower():
            rob_s3 = p
            break
    comparisons.append({
        "scene": "3. Диалог Эдварда и Эмметта (POV и род глаголов)",
        "en": en_s3,
        "gemini": gem_s3,
        "robsten": rob_s3,
        "notes": "Критическая ошибка Gemini: перевел слова Эдварда в женском роде ('рявкнула я, отшвыривая его руку... я не могла дождаться'), так как не знал о смене POV. У Robsten идеальный мужской род: 'огрызнулся я, сбрасывая его руку... я не мог дождаться'."
    })

    # Scene 4: Chapter 2 Cafeteria / "Edward Cullen"
    en_s4 = "\"Edward Cullen,\" he answered distractedly, eyes scanning the room. ... He didn't even look at me. Just turned and walked away."
    gem_s4 = ""
    for p in gemini_ch2_text.split('\n\n'):
        if 'эдвард каллен' in p.lower():
            gem_s4 = p
            break
    rob_s4 = ""
    for p in robsten_ch2['sections'][0]['text'].split('\n\n'):
        if 'эдвард каллен' in p.lower():
            rob_s4 = p
            break
    comparisons.append({
        "scene": "4. Глава 2: Диалог в столовой (переход к Эдварду)",
        "en": en_s4,
        "gemini": gem_s4,
        "robsten": rob_s4,
        "notes": "У Robsten четкая граница перехода: часть 1 заканчивается словами Беллы, часть 2 сразу подхватывает Эдварда ('Я поднял голову от наброска...')."
    })

    return comparisons

comps = extract_side_by_side()

# Write detailed markdown report
report_path = r'E:\AI-Dubbing\output\wide_awake\translation_comparison_report.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(comps, f, ensure_ascii=False, indent=2)

print("Comparison extracted successfully to:", report_path)
