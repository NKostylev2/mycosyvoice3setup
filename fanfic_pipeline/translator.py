import os
import time
import json
import requests
from typing import List

from fanfic_pipeline.config import (
    TOKENWAVE_API_KEY,
    TOKENWAVE_BASE_URL,
    GEMINI_MODEL,
    get_translation_system_prompt,
)

class ChapterTranslator:
    def __init__(
        self,
        api_key: str = TOKENWAVE_API_KEY,
        base_url: str = TOKENWAVE_BASE_URL,
        model: str = GEMINI_MODEL,
        pov: str = "bella",
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.pov = pov
        self.system_prompt = get_translation_system_prompt(pov)

    def _call_gemini(self, text: str, max_retries: int = 3) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Translate the following text into Russian:\n\n{text}"},
            ],
            "temperature": 0.3,
        }

        for attempt in range(max_retries):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return content.strip()
                else:
                    print(f"[Warning] Translation request returned status {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"[Warning] Translation error on attempt {attempt+1}/{max_retries}: {e}")
            time.sleep(2 * (attempt + 1))

        raise RuntimeError("Failed to translate chunk after retries.")

    def translate_paragraphs(self, paragraphs: List[str], cache_file: str = None) -> List[str]:
        """
        Translates a list of paragraphs in batches (~2500-3500 chars per batch).
        Saves cache to disk to resume seamlessly if stopped.
        """
        cached_results = {}
        if cache_file and os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_results = json.load(f)
                print(f"Loaded {len(cached_results)} translated chunks from cache.")
            except Exception as e:
                print(f"Could not load cache: {e}")

        # Group paragraphs into chunks
        chunks = []
        current_chunk_indices = []
        current_chunk_chars = 0

        for idx, p in enumerate(paragraphs):
            p_len = len(p)
            if current_chunk_chars + p_len > 3000 and current_chunk_indices:
                chunks.append(current_chunk_indices)
                current_chunk_indices = [idx]
                current_chunk_chars = p_len
            else:
                current_chunk_indices.append(idx)
                current_chunk_chars += p_len
        if current_chunk_indices:
            chunks.append(current_chunk_indices)

        translated_paragraphs = [""] * len(paragraphs)

        for chunk_idx, p_indices in enumerate(chunks):
            chunk_key = f"chunk_{p_indices[0]}_{p_indices[-1]}_{len(p_indices)}"
            if chunk_key in cached_results:
                chunk_trans = cached_results[chunk_key]
            else:
                chunk_text = "\n\n".join([f"[[P{i}]] {paragraphs[i]}" for i in p_indices])
                chunk_prompt = (
                    f"Translate the following paragraphs. Preserve the tag format [[P<number>]] at the beginning of each paragraph so they can be matched:\n\n{chunk_text}"
                )
                print(f"Translating batch {chunk_idx + 1}/{len(chunks)} ({len(p_indices)} paragraphs)...")
                chunk_trans = self._call_gemini(chunk_prompt)
                cached_results[chunk_key] = chunk_trans
                if cache_file:
                    os.makedirs(os.path.dirname(os.path.abspath(cache_file)), exist_ok=True)
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(cached_results, f, ensure_ascii=False, indent=2)

            # Parse [[P<i>]] from translated text
            for i in p_indices:
                tag = f"[[P{i}]]"
                if tag in chunk_trans:
                    # extract between this tag and next
                    start = chunk_trans.find(tag) + len(tag)
                    next_pos = len(chunk_trans)
                    # find if there is any other tag after
                    for j in p_indices:
                        if j != i:
                            pos = chunk_trans.find(f"[[P{j}]]", start)
                            if 0 <= pos < next_pos:
                                next_pos = pos
                    translated_paragraphs[i] = chunk_trans[start:next_pos].strip()
                else:
                    # Fallback: if tag missing, translate single paragraph directly
                    print(f"Fallback direct translation for P{i}...")
                    p_single = self._call_gemini(paragraphs[i])
                    translated_paragraphs[i] = p_single.strip()

        return translated_paragraphs

if __name__ == "__main__":
    from fanfic_pipeline.pdf_parser import FanficPDFParser
    parser = FanficPDFParser()
    _, text = parser.extract_chapter_text(1)
    paras = text.split("\n\n")[:3]
    translator = ChapterTranslator()
    trans = translator.translate_paragraphs(paras)
    for orig, tr in zip(paras, trans):
        print("ORIGINAL:", orig[:80])
        print("TRANSLATION:", tr[:80])
        print("-" * 50)
