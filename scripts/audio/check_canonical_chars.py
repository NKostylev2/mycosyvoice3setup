import json

with open(r'E:\AI-Dubbing\knowledge\canonical\characters_main.json', 'r', encoding='utf-8') as f:
    main_chars = json.load(f)

print("Main characters:")
for c in main_chars:
    print(c.get('character_id'), c.get('name_en'), c.get('name_ru'), c.get('voice_direction'))
