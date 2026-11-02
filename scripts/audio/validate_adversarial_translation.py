"""
Phase 6C -- Deterministic structural validator for adversarial translation audit.
Checks ONLY objective/structural properties. Does NOT attempt semantic equivalence.
"""
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path

WORK = Path(r'E:\AI-Dubbing\work\S01E01')
INPUT = Path(r'E:\AI-Dubbing\input')

def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

print('=' * 70)
print('PHASE 6C STRUCTURAL VALIDATOR')
print('=' * 70)
print()

errors = []

# 1. JSON VALIDITY
try:
    dubbing_input = load_json(WORK / 'russian_dubbing_input.json')
    print('[PASS] russian_dubbing_input.json is valid JSON')
except Exception as e:
    print(f'[FAIL] russian_dubbing_input.json: {e}')
    errors.append('dubbing_input_invalid_json')

try:
    adaptation = load_json(WORK / 'russian_dubbing_adaptation.json')
    print('[PASS] russian_dubbing_adaptation.json is valid JSON')
except Exception as e:
    print(f'[FAIL] russian_dubbing_adaptation.json: {e}')
    errors.append('adaptation_invalid_json')

try:
    draft = load_json(WORK / 'russian_translation_draft.json')
    print('[PASS] russian_translation_draft.json is valid JSON')
except Exception as e:
    print(f'[FAIL] russian_translation_draft.json: {e}')
    errors.append('draft_invalid_json')

try:
    canonical = load_json(WORK / 'canonical_dialogue_final.json')
    print('[PASS] canonical_dialogue_final.json is valid JSON')
except Exception as e:
    print(f'[FAIL] canonical_dialogue_final.json: {e}')
    errors.append('canonical_invalid_json')

try:
    timeline = load_json(WORK / 'timeline_v2.json')
    print('[PASS] timeline_v2.json is valid JSON')
except Exception as e:
    print(f'[FAIL] timeline_v2.json: {e}')
    errors.append('timeline_invalid_json')

print()

input_uids = [u['utterance_id'] for u in dubbing_input['utterances']]
adapt_uids = [u['utterance_id'] for u in adaptation['utterances']]
draft_uids = [u['utterance_id'] for u in draft['utterances']]
canon_uids = [u['utterance_id'] for u in canonical['utterances']]

print(f'Counts: input={len(input_uids)}, adapt={len(adapt_uids)}, draft={len(draft_uids)}, canon={len(canon_uids)}')

if set(input_uids) == set(adapt_uids) == set(draft_uids) == set(canon_uids):
    print('[PASS] UID sets match across all files')
else:
    print('[FAIL] UID mismatch')
    errors.append('uid_mismatch')

for name, uids in [('input', input_uids), ('adapt', adapt_uids)]:
    if len(uids) != len(set(uids)):
        print(f'[FAIL] Duplicate UIDs in {name}')
        errors.append(f'dup_{name}')
    else:
        print(f'[PASS] No duplicate UIDs in {name}')

print()

input_by_uid = {u['utterance_id']: u for u in dubbing_input['utterances']}
canon_by_uid = {u['utterance_id']: u for u in canonical['utterances']}
adapt_by_uid = {u['utterance_id']: u for u in adaptation['utterances']}

# TIMING INVARIANCE
t_issues = 0
for uid in input_uids:
    inp = input_by_uid[uid]
    can = canon_by_uid.get(uid)
    if can:
        cs = can.get('timing', {}).get('acoustic_start')
        ce = can.get('timing', {}).get('acoustic_end')
        if cs is not None and abs(inp['acoustic_start'] - cs) > 0.001:
            t_issues += 1
        if ce is not None and abs(inp['acoustic_end'] - ce) > 0.001:
            t_issues += 1

if t_issues:
    print(f'[FAIL] Timing invariance violations: {t_issues}')
    errors.append('timing')
else:
    print('[PASS] Timing invariance OK')

# DOWNSTREAM CONSISTENCY
stale = 0
for uid in input_uids:
    inp = input_by_uid[uid]
    adp = adapt_by_uid.get(uid, {})
    if adp.get('adapted_ru') and inp['adapted_ru'] != adp['adapted_ru']:
        stale += 1

if stale:
    print(f'[FAIL] Stale adapted_ru: {stale}')
    errors.append('stale')
else:
    print('[PASS] Downstream consistency OK')

# EMPTY adapted_ru
empty = sum(1 for u in dubbing_input['utterances'] if not u.get('adapted_ru','').strip())
if empty:
    print(f'[FAIL] Empty adapted_ru: {empty}')
    errors.append('empty_adapted')
else:
    print('[PASS] All adapted_ru non-empty')

blocked = [u['utterance_id'] for u in dubbing_input['utterances'] if u.get('translation_blocked')]
print(f'Blocked: {len(blocked)} ({", ".join(blocked)})')

print()
print('=' * 70)
if errors:
    print(f'RESULT: FAIL ({len(errors)} issues: {", ".join(errors)})')
else:
    print('RESULT: ALL STRUCTURAL CHECKS PASSED')
print('=' * 70)
