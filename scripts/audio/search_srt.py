with open(r'E:\AI-Dubbing-Subtitles\output\S01E01.en.srt', 'r', encoding='utf-8') as f:
    text = f.read()

entries = text.strip().split('\n\n')
print(f"Total SRT entries: {len(entries)}")

for e in entries:
    lines = e.strip().split('\n')
    if len(lines) >= 3:
        idx = lines[0]
        time_str = lines[1]
        content = " ".join(lines[2:])
        # Let's search for any monster roar, creature line, or dialogue
        # in the climax or fight scenes
        if any(w in content.lower() for w in ['naughty', 'bogey', 'boogey', 'book', 'worm', 'children', 'leave', 'never', 'run', 'hide']):
            print(f"[{idx}] {time_str}: {content}")
