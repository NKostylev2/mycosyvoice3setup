"""
Profanity filter and euphemism replacer for fanfic dubbing.
Replaces Russian obscenities (мат) and harsh vulgarisms with expressive literary equivalents
(черт, чертов, проклятый, долбаный, блин, зараза, дрянь, кошмар, плевать, к черту).
"""

import re
from typing import Tuple, List

# Dictionary of direct and inflectional replacements
# Key: lowercase word/phrase, Value: replacement (lowercase)
INFLECTION_MAP = {
    # Гребаный -> Чертов
    "гребаный": "чертов",
    "гребанная": "чертова",
    "гребаная": "чертова",
    "гребаное": "чертово",
    "гребанное": "чертово",
    "гребаного": "чертова",
    "гребанного": "чертова",
    "гребаному": "чертовому",
    "гребанному": "чертовому",
    "гребаным": "чертовым",
    "гребанным": "чертовым",
    "гребаном": "чертовом",
    "гребанном": "чертовом",
    "гребаной": "чертовой",
    "гребанной": "чертовой",
    "гребаную": "чертову",
    "гребанную": "чертову",
    "гребаные": "чертовы",
    "гребанные": "чертовы",
    "гребаных": "чертовых",
    "гребанных": "чертовых",
    "гребаными": "чертовыми",
    "гребанными": "чертовыми",

    # Ёбаный / Ебаный -> Проклятый / Чертов
    "ебаный": "чертов",
    "ёбаный": "чертов",
    "ебаная": "чертова",
    "ёбаная": "чертова",
    "ебаное": "чертово",
    "ёбаное": "чертово",
    "ебаного": "чертова",
    "ёбаного": "чертова",
    "ебаному": "чертовому",
    "ёбаному": "чертовому",
    "ебаным": "чертовым",
    "ёбаным": "чертовым",
    "ебаном": "чертовом",
    "ёбаном": "чертовом",
    "ебаной": "чертовой",
    "ёбаной": "чертовой",
    "ебаную": "чертову",
    "ёбаную": "чертову",
    "ебаные": "чертовы",
    "ёбаные": "чертовы",
    "ебаных": "чертовых",
    "ёбаных": "чертовых",

    # Блядский
    "блядский": "чертовский",
    "блядская": "чертовская",
    "блядское": "чертовское",
    "блядские": "чертовские",
    "блядского": "чертовского",
    "блядской": "чертовской",
    "блядскую": "чертовскую",
    "блядских": "чертовских",

    # Сукин
    "сукин": "чертов",
    "сукина": "чертова",
    "сукины": "чертовы",
    "сукиных": "чертовых",

    # Сука (в роли ругательства)
    "сука": "дрянь",
    "суки": "твари",
    "суку": "дрянь",
    "сукой": "дрянью",
    "суке": "дряни",

    # Хуйня
    "хуйня": "ерунда",
    "хуйни": "ерунды",
    "хуйне": "ерунде",
    "хуйню": "ерунду",
    "хуйней": "ерундой",
    "хуйнёй": "ерундой",

    # Пиздец
    "пиздец": "кошмар",
    "распиздяй": "разгильдяй",

    # English words
    "fuck": "черт",
    "fucking": "чертов",
    "shit": "дерьмо",
    "holy shit": "святые угодники",
}

# Regex phrase replacements (ordered: specific phrases first, then single words)
PHRASE_REPLACEMENTS = [
    # Куда, бля, ... / Как, бля, ...
    (r"\bКуда,\s*бля,?\b", "Куда, черт возьми,"),
    (r"\bкуда,\s*бля,?\b", "куда, черт возьми,"),
    (r"\bКак,\s*бля,?\b", "Как, черт подери,"),
    (r"\bкак,\s*бля,?\b", "как, черт подери,"),
    (r"\bГде,\s*бля,?\b", "Где, черт возьми,"),
    (r"\bгде,\s*бля,?\b", "где, черт возьми,"),
    (r"\bЧто,\s*бля,?\b", "Что, черт подери,"),
    (r"\bчто,\s*бля,?\b", "что, черт подери,"),
    (r"\bКто,\s*бля,?\b", "Кто, черт подери,"),
    (r"\bкто,\s*бля,?\b", "кто, черт подери,"),

    # Standalone 'бля' or 'блять' or 'блядь' with commas
    # Sentence or line start:
    (r"(?:^|(?<=[.!?…]\s))\s*[Бб]ля\b,?\s*", "Черт возьми, "),
    (r"(?:^|(?<=[.!?…]\s))\s*[Бб]лять\b,?\s*", "Черт подери, "),
    (r"(?:^|(?<=[.!?…]\s))\s*[Бб]лядь\b,?\s*", "Черт подери, "),
    # Preceded by comma:
    (r",\s*[Бб]ля\b,?\s*", ", черт возьми, "),
    (r",\s*[Бб]лять\b,?\s*", ", черт подери, "),
    (r",\s*[Бб]лядь\b,?\s*", ", черт подери, "),
    # General word boundary fallback:
    (r"\b[Бб]ля\b,?\s*", "черт возьми, "),
    (r"\b[Бб]лять\b,?\s*", "черт подери, "),
    (r"\b[Бб]лядь\b,?\s*", "черт подери, "),

    # Хуй phrases
    (r"\b[Кк]акого\s+хуя\b", "какого черта"),
    (r"\b[Нн]а\s*хуй\b", "к черту"),
    (r"\b[Нн]ахуй\b", "к черту"),
    (r"\b[Пп]о\s*хуй\b", "плевать"),
    (r"\b[Пп]охуй\b", "плевать"),
    (r"\b[Пп]о\s*хую\b", "плевать"),
    (r"\b[Нн]и\s*хуя\b", "ни черта"),
    (r"\b[Нн]ихуя\b", "ни черта"),
    (r"\b[Дд]о\s*хуя\b", "до черта"),
    (r"\b[Дд]охуя\b", "до черта"),
    (r"\b[Оо]хуеть\b", "обалдеть"),
    (r"\b[Оо]хуел([аио]?)\b", r"обалдел\1"),

    # Ебать phrases
    (r"\b[Ее]бать\b", "черт возьми"),
    (r"\b[Зз]аебал([аио]?)\b", r"достал\1"),
    (r"\b[Зз]аебись\b", "зашибись"),
    (r"\b[Рр]азъебал([аио]?)\b", r"разнес\1"),
    (r"\b[Вв]ъебал([аио]?)\b", r"врезал\1"),

    # Пизд-
    (r"\b[Пп]издец\b", "кошмар"),
    (r"\b[Пп]изд([еи])т\b", r"вр\1т"),
    (r"\b[Сс]пиздил([аио]?)\b", r"стащил\1"),

    # English phrases
    (r"\bHoly\s+shit\b", "Святые угодники", re.IGNORECASE),
    (r"\bFuck!\b", "Черт!"),
    (r"\bfuck!\b", "черт!"),
    (r"\bFuck\b", "Черт"),
    (r"\bfuck\b", "черт"),
]


def match_case(original: str, replacement: str) -> str:
    """Preserve casing: Titlecase, UPPERCASE, or lowercase."""
    if original.isupper():
        return replacement.upper()
    elif original and original[0].isupper():
        return replacement.capitalize()
    return replacement


def censor_line(line: str) -> Tuple[str, List[str]]:
    applied = []
    result = line

    # 1. Phrase replacements
    for item in PHRASE_REPLACEMENTS:
        pattern = item[0]
        replacement = item[1]
        flags = item[2] if len(item) > 2 else 0

        def _sub_phrase(m):
            orig = m.group(0)
            rep = match_case(orig, replacement)
            applied.append(f"'{orig}' -> '{rep}'")
            return rep

        result = re.sub(pattern, _sub_phrase, result, flags=flags)

    # 2. Inflection map
    words = re.findall(r"\b[\w-]+\b", result)
    for word in set(words):
        low = word.lower()
        if low in INFLECTION_MAP:
            rep = INFLECTION_MAP[low]
            matched_rep = match_case(word, rep)
            pattern = r"\b" + re.escape(word) + r"\b"
            result = re.sub(pattern, matched_rep, result)
            applied.append(f"'{word}' -> '{matched_rep}'")

    # Clean double commas, leading commas, and punctuation spacing
    result = re.sub(r",\s*,+", ",", result)
    result = re.sub(r"([.!?…])\s*,+", r"\1 ", result)
    result = re.sub(r"!\s*!", "!", result)
    result = re.sub(r"[ \t]+", " ", result).strip()
    result = re.sub(r"^[,\s]+", "", result).strip()

    # Capitalize start of line if needed
    if result and result[0].islower():
        result = result[0].upper() + result[1:]
    result = re.sub(r"([.!?…]\s+)([a-zа-яё])", lambda m: m.group(1) + m.group(2).upper(), result)

    return result, applied


def censor_text(text: str) -> Tuple[str, List[str]]:
    """
    Clean obscenities/profanities from multiline text, preserving paragraphs.
    Returns: (cleaned_text, list_of_replacements_applied)
    """
    lines = text.split("\n")
    cleaned_lines = []
    all_applied = []

    for line in lines:
        if not line.strip():
            cleaned_lines.append("")
            continue
        c_line, reps = censor_line(line)
        cleaned_lines.append(c_line)
        all_applied.extend(reps)

    return "\n".join(cleaned_lines), all_applied
