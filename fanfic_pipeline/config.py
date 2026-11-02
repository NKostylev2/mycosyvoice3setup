import os

# Base paths
BASE_DIR = r"E:\AI-Dubbing"
PDF_PATH = r"M:\Downloads\Telegram Desktop\Wide Awake by AngstGoddess003.pdf"
VOICES_DIR = os.path.join(BASE_DIR, "alltalk_tts", "voices")
DEFAULT_VOICE = os.path.join(VOICES_DIR, "female_03.wav")

WORK_DIR = os.path.join(BASE_DIR, "work", "wide_awake")
OUTPUT_DIR = os.path.join(BASE_DIR, "output", "wide_awake")

# CosyVoice paths
COSYVOICE_DIR = os.path.join(BASE_DIR, "CosyVoice")
COSYVOICE_MODEL_DIR = os.path.join(COSYVOICE_DIR, "pretrained_models", "Fun-CosyVoice3-0.5B")

# TokenWave Gemini API configuration
TOKENWAVE_API_KEY = "sk-4iOcQ82WDdvpIOOXo3a76O11L2NjlnHCL2AtbPxvdJT8vkdc"
TOKENWAVE_BASE_URL = "https://api.tokenwave.ru/v1"
GEMINI_MODEL = "gemini-3.8-flash"

# POV Profiles and Prompts
POV_PROFILES = {
    "bella": {
        "voice": os.path.join(VOICES_DIR, "female_03.wav"),
        "pov_desc": "Bella Swan (female POV)",
        "verb_gender_instruction": "All first-person past tense verbs MUST be FEMININE in Russian (я посмотрела, я подумала, я вздохнула, я почувствовала, я была).",
        "tts_instruct": (
            "You are a professional female audiobook narrator reading a novel with a calm, steady, clear voice, "
            "consistent timbre, and even, natural pacing.<|endofprompt|>"
        ),
    },
    "edward": {
        "voice": os.path.join(VOICES_DIR, "male_05.wav"),
        "pov_desc": "Edward Cullen (male POV)",
        "verb_gender_instruction": "All first-person past tense verbs MUST be MASCULINE in Russian (я посмотрел, я подумал, я вздохнул, я почувствовал, я был).",
        "tts_instruct": (
            "You are Edward Cullen, a 17-year-old young man with a calm, deep, expressive voice, "
            "reading a dramatic story from his perspective in clear, natural Russian.<|endofprompt|>"
        ),
    },
}

def get_translation_system_prompt(pov: str = "bella") -> str:
    profile = POV_PROFILES.get(pov.lower(), POV_PROFILES["bella"])
    return f"""You are a master literary translator specializing in romantic and dramatic fiction.
Translate the following excerpt from English to Russian.

Guidelines:
1. POV: The story is told from the first-person perspective of {profile['pov_desc']}.
   - {profile['verb_gender_instruction']}
2. TONE & STYLE: Natural, expressive, modern literary Russian. Avoid clumsy literalisms and false friends (e.g., melodramatic -> мелодраматичной, NOT меломанкой). Preserve the slang, emotional intensity, sarcasm, and dark humor.
3. NAMES & TERMS:
   - Bella Swan -> Белла Свон
   - Edward Cullen -> Эдвард Каллен
   - Carlisle -> Карлайл
   - Alice -> Элис
   - Jasper -> Джаспер
   - Rosalie -> Розали
   - Emmett -> Эмметт
   - Esme -> Эсми (или Эзми)
   - Charlie -> Чарли
   - Renée -> Рене
   - Forks -> Форкс
   - Phoenix -> Финикс
4. FORMAT: Return ONLY the translated Russian text. Do not add explanations, translator notes, or markdown formatting unless present in the original.
"""

DEFAULT_TTS_INSTRUCT = POV_PROFILES["bella"]["tts_instruct"]
DEFAULT_SEED = 42
