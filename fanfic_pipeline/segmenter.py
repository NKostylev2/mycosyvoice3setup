import re
from typing import List, Dict, Optional, Any
import razdel

class SentenceSegmenter:
    """
    Token-aware and Russian-friendly sentence segmenter.
    Preserves 'ё', punctuation, quotation marks, and word endings.
    Combines sentences into natural, coherent breath blocks (60-80 tokens).
    Prevents generation failure caused by segments being too short (< 0.5 * prompt_length).
    """

    def __init__(
        self,
        tokenizer: Optional[Any] = None,
        min_tokens: int = 60,
        max_tokens: int = 85,
        min_block_tokens: int = 40,
        # Legacy parameters for backward compatibility:
        min_sentence_len: int = 50,
        max_sentence_len: int = 180,
    ):
        self.tokenizer = tokenizer
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.min_block_tokens = min_block_tokens
        self.min_sentence_len = min_sentence_len
        self.max_sentence_len = max_sentence_len

    def count_tokens(self, text: str) -> int:
        """
        Calculates token count using the model's tokenizer if available,
        or an accurate character-to-token ratio for Russian text.
        """
        if not text:
            return 0
        if self.tokenizer is not None:
            try:
                tokens = self.tokenizer.encode(text)
                return len(tokens)
            except Exception:
                pass
        # Fallback approximation for Russian Qwen2 tokenizer: ~2.5 characters per token
        return max(1, int(len(text) / 2.5))

    def _clean_text(self, text: str) -> str:
        """
        Cleans excessive whitespace while preserving 'ё', punctuation,
        quotes, and exact endings.
        """
        t = text.strip()
        t = re.sub(r'[ \t]+', ' ', t)
        t = re.sub(r'\s*—\s*', ' — ', t)
        return t.strip()

    def _split_oversized_sentence(self, sentence: str) -> List[str]:
        """
        Breaks an exceptionally long sentence (> max_tokens) at natural clause boundaries
        (semicolons, dashes, or conjunctions like ', но', ', а', ', что', ', когда').
        Does NOT break ordinary sentences.
        """
        parts = re.split(
            r'([;\n]| — |\s*,\s*(?:но|а|что|когда|хотя|потому что|так что|чтобы|если)\s+)',
            sentence
        )
        if len(parts) <= 1:
            return [sentence]

        chunks = []
        cur = ""
        for p in parts:
            if not p:
                continue
            tentative = cur + p
            if self.count_tokens(tentative) <= self.max_tokens:
                cur = tentative
            else:
                if cur.strip():
                    chunks.append(cur.strip())
                cur = p
        if cur.strip():
            chunks.append(cur.strip())

        return chunks if chunks else [sentence]

    def split_paragraph(self, paragraph: str, p_idx: int = 0) -> List[Dict]:
        """
        Splits a single paragraph into 60-80 token blocks.
        """
        clean_para = paragraph.strip()
        if not clean_para:
            return []

        raw_sentences = [
            self._clean_text(s.text)
            for s in razdel.sentenize(clean_para)
            if s.text.strip()
        ]
        if not raw_sentences:
            return []

        atom_sentences = []
        for s in raw_sentences:
            if self.count_tokens(s) > self.max_tokens:
                atom_sentences.extend(self._split_oversized_sentence(s))
            else:
                atom_sentences.append(s)

        blocks = []
        cur_block = []
        cur_tokens = 0

        for s in atom_sentences:
            s_tok = self.count_tokens(s)
            if not cur_block:
                cur_block.append(s)
                cur_tokens = s_tok
                continue

            if cur_tokens + s_tok <= self.max_tokens:
                cur_block.append(s)
                cur_tokens += s_tok
            elif cur_tokens < self.min_tokens and (cur_tokens + s_tok <= self.max_tokens + 15):
                cur_block.append(s)
                cur_tokens += s_tok
            else:
                blocks.append(" ".join(cur_block))
                cur_block = [s]
                cur_tokens = s_tok

        if cur_block:
            if blocks and cur_tokens < self.min_block_tokens:
                prev_tokens = self.count_tokens(blocks[-1])
                if prev_tokens + cur_tokens <= (self.max_tokens + 20):
                    blocks[-1] = blocks[-1] + " " + " ".join(cur_block)
                else:
                    blocks.append(" ".join(cur_block))
            else:
                blocks.append(" ".join(cur_block))

        results = []
        for s_idx, b_text in enumerate(blocks):
            clean_b = self._clean_text(b_text)
            if not clean_b:
                continue
            is_last = (s_idx == len(blocks) - 1)
            results.append({
                "p_idx": p_idx,
                "s_idx": s_idx,
                "text": clean_b,
                "tokens": self.count_tokens(clean_b),
                "is_last_in_p": is_last,
            })
        return results

    def segment_chapter(self, paragraphs: List[str]) -> List[Dict]:
        """
        Segments chapter by accumulating sentences into balanced 60-80 token blocks,
        intelligently merging short paragraphs/dialogues to prevent premature EOS.
        """
        all_sentences = []
        for p_idx, p in enumerate(paragraphs):
            clean_p = p.strip()
            if not clean_p:
                continue
            s_list = [self._clean_text(s.text) for s in razdel.sentenize(clean_p) if s.text.strip()]
            for s_idx, s in enumerate(s_list):
                if self.count_tokens(s) > self.max_tokens:
                    sub_parts = self._split_oversized_sentence(s)
                    for sp_idx, sp in enumerate(sub_parts):
                        all_sentences.append({
                            "text": sp,
                            "p_idx": p_idx,
                            "is_last_in_p": (s_idx == len(s_list) - 1 and sp_idx == len(sub_parts) - 1),
                            "tokens": self.count_tokens(sp)
                        })
                else:
                    all_sentences.append({
                        "text": s,
                        "p_idx": p_idx,
                        "is_last_in_p": (s_idx == len(s_list) - 1),
                        "tokens": self.count_tokens(s)
                    })

        if not all_sentences:
            return []

        blocks = []
        cur_items = []
        cur_tokens = 0

        for item in all_sentences:
            tok = item["tokens"]
            if not cur_items:
                cur_items.append(item)
                cur_tokens = tok
                continue

            if cur_tokens + tok <= self.max_tokens:
                cur_items.append(item)
                cur_tokens += tok
            elif cur_tokens < self.min_tokens and (cur_tokens + tok <= self.max_tokens + 15):
                cur_items.append(item)
                cur_tokens += tok
            else:
                block_text = self._clean_text(" ".join([x["text"] for x in cur_items]))
                is_last_in_p = cur_items[-1]["is_last_in_p"]
                p_idx = cur_items[-1]["p_idx"]
                blocks.append({
                    "p_idx": p_idx,
                    "s_idx": len(blocks),
                    "text": block_text,
                    "tokens": self.count_tokens(block_text),
                    "is_last_in_p": is_last_in_p,
                })
                cur_items = [item]
                cur_tokens = tok

        if cur_items:
            # Handle final block
            if blocks and cur_tokens < self.min_block_tokens:
                prev_text = blocks[-1]["text"]
                prev_tok = blocks[-1]["tokens"]
                if prev_tok + cur_tokens <= (self.max_tokens + 25):
                    merged_text = self._clean_text(prev_text + " " + " ".join([x["text"] for x in cur_items]))
                    blocks[-1]["text"] = merged_text
                    blocks[-1]["tokens"] = self.count_tokens(merged_text)
                    blocks[-1]["is_last_in_p"] = cur_items[-1]["is_last_in_p"]
                else:
                    block_text = self._clean_text(" ".join([x["text"] for x in cur_items]))
                    blocks.append({
                        "p_idx": cur_items[-1]["p_idx"],
                        "s_idx": len(blocks),
                        "text": block_text,
                        "tokens": self.count_tokens(block_text),
                        "is_last_in_p": cur_items[-1]["is_last_in_p"],
                    })
            else:
                block_text = self._clean_text(" ".join([x["text"] for x in cur_items]))
                blocks.append({
                    "p_idx": cur_items[-1]["p_idx"],
                    "s_idx": len(blocks),
                    "text": block_text,
                    "tokens": self.count_tokens(block_text),
                    "is_last_in_p": cur_items[-1]["is_last_in_p"],
                })

        return blocks
