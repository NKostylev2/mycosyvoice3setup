"""
Russian ordinal number to words converter for chapter and part announcements.
Feminine gender used for 'глава' and 'часть'.
"""

ORDINALS_FEMININE = {
    1: "первая",
    2: "вторая",
    3: "третья",
    4: "четвёртая",
    5: "пятая",
    6: "шестая",
    7: "седьмая",
    8: "восьмая",
    9: "девятая",
    10: "десятая",
    11: "одиннадцатая",
    12: "двенадцатая",
    13: "тринадцатая",
    14: "четырнадцатая",
    15: "пятнадцатая",
    16: "шестнадцатая",
    17: "семнадцатая",
    18: "восемнадцатая",
    19: "девятнадцатая",
    20: "двадцатая",
    21: "двадцать первая",
    22: "двадцать вторая",
    23: "двадцать третья",
    24: "двадцать четвёртая",
    25: "двадцать пятая",
    26: "двадцать шестая",
    27: "двадцать седьмая",
    28: "двадцать восьмая",
    29: "двадцать девятая",
    30: "тридцатая",
    31: "тридцать первая",
    32: "тридцать вторая",
    33: "тридцать третья",
    34: "тридцать четвёртая",
    35: "тридцать пятая",
    36: "тридцать шестая",
    37: "тридцать седьмая",
    38: "тридцать восьмая",
    39: "тридцать девятая",
    40: "сороковая",
    41: "сорок первая",
    42: "сорок вторая",
    43: "сорок третья",
    44: "сорок четвёртая",
    45: "сорок пятая",
    46: "сорок шестая",
    47: "сорок седьмая",
    48: "сорок восьмая",
    49: "сорок девятая",
    50: "пятидесятая",
    51: "пятьдесят первая",
    52: "пятьдесят вторая",
}


def get_ordinal_f(n: int) -> str:
    """Return Russian feminine ordinal for number n (1 -> первая)."""
    return ORDINALS_FEMININE.get(n, str(n))


def get_section_announcement(
    chapter_num: int,
    sec_idx: int,
    pov: str,
    start_num: int = None,
    end_num: int = None,
    chapter_title: str = None
) -> str:
    """
    Generate Russian spoken announcement for a section:
    - At start of chapter (sec_idx == 0):
        'Глава первая. Рыжие Сдобные Зомби. Часть первая. Белла.'
    - At subsequent sections (sec_idx > 0):
        'Часть вторая. Эдвард.'
    """
    char_name = "Белла" if pov.lower() == "bella" else "Эдвард"
    part_word = get_ordinal_f(sec_idx + 1)

    if sec_idx == 0:
        if chapter_num >= 999:
            ch_word = "Эпилог"
            if chapter_title:
                clean_title = chapter_title.strip(" .")
                return f"{ch_word}. {clean_title}. Часть {part_word}. {char_name}."
            return f"{ch_word}, часть {part_word}. {char_name}."
        elif start_num and end_num and start_num != end_num:
            ch_word = f"{get_ordinal_f(start_num)} — {get_ordinal_f(end_num)}"
        else:
            ch_word = get_ordinal_f(chapter_num)

        if chapter_title:
            clean_title = chapter_title.strip(" .")
            if "ШОК" in clean_title:
                clean_title = clean_title.replace("ШОК", "Шок")
            return f"Глава {ch_word}. {clean_title}. Часть {part_word}. {char_name}."
        return f"Глава {ch_word}, часть {part_word}. {char_name}."
    else:
        return f"Часть {part_word}. {char_name}."


if __name__ == "__main__":
    print("Chapter 1, Sec 0 (Bella):", get_section_announcement(1, 0, "bella"))
    print("Chapter 1, Sec 1 (Edward):", get_section_announcement(1, 1, "edward"))
    print("Chapter 1, Sec 2 (Bella):", get_section_announcement(1, 2, "bella"))
    print("Chapter 1, Sec 3 (Edward):", get_section_announcement(1, 3, "edward"))
    print("Chapter 26-27, Sec 0 (Bella):", get_section_announcement(26, 0, "bella", 26, 27))
