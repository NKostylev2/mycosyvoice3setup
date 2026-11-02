import json

with open(r'E:\AI-Dubbing-Subtitles\output\S01E01.timeline.final.json', 'r', encoding='utf-8') as f:
    tl_data = json.load(f)

records = tl_data['records']

# Let's inspect the distribution of speakers in the episode
# Main characters:
# Martin, Diana, Java, Billy, M.O.M.
# Secondary characters:
# Librarian (Nelly's Father), Nelly, Ian's Mother, Townsperson, Bogeyman

print("Total records in timeline:", len(records))
print("First record:", records[0]['dialogue_id'], records[0]['source']['text'])
print("Last record:", records[-1]['dialogue_id'], records[-1]['source']['text'])
