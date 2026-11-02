# AI Agent System Instructions: CosyVoice 3 Russian Speech Synthesis & Dubbing

> **Purpose:** This specification document is designed for AI coding assistants, autonomous agents, and LLMs working with the CosyVoice 3 model (`Fun-CosyVoice3-0.5B-2512`) on Russian speech synthesis, audiobook creation, and multi-speaker dubbing.

---

## 1. Core Architecture & Inference Rules

### 1.1 Model Identity & Sample Rate
- **Model:** `FunAudioLLM/CosyVoice` 3.0 (specifically `Fun-CosyVoice3-0.5B-2512` or `Fun-CosyVoice3-0.5B`).
- **Sample Rate:** `24000 Hz` (do not downsample or upsample the master audio).
- **Core LLM Backbone:** Qwen2 architecture.

### 1.2 Mandatory Inference Parameters
When calling `inference_zero_shot`, ALWAYS use the following settings:
```python
outputs = cosyvoice.inference_zero_shot(
    tts_text=text_chunk,
    prompt_text=prompt_text,
    prompt_wav=ref_wav_path,
    stream=False,          # DO NOT use streaming for master audiobook rendering
    speed=1.0,             # Keep 1.0; slowing down via model may distort phonemes
    text_frontend=False    # MANDATORY: disables CosyVoice internal frontend which corrupts Russian
)
```

### 1.3 Zero-Shot Prompt Formatting
CosyVoice 3 requires the `<|endofprompt|>` special token (`151646` in Qwen2 vocabulary) between the system role and the reference transcript:
```python
# CORRECT zero-shot prompt format:
prompt_text = f"You are a helpful assistant.<|endofprompt|>{ref_transcript}"
```
*Never pass bare text without `<|endofprompt|>`, as it breaks context alignment in the autoregressive stage.*

---

## 2. Russian Text Preprocessing & Token-Aware Segmentation

### 2.1 The Problem of Swallowed Endings
CosyVoice 3 exhibits EOS (end-of-sentence) premature termination when:
1. Segments are too short (`len(text) < 0.5 * len(prompt_text)`).
2. The internal regex frontend cuts text arbitrarily, breaking syllables.
3. Sentence boundaries lack contextual lookahead.

### 2.2 Segmentation Algorithm (`SentenceSegmenter`)
Do **NOT** use character-based slicing (`[:200]`). Use `fanfic_pipeline.segmenter.SentenceSegmenter`:
- **Underlying Tokenizer:** `transformers.AutoTokenizer` / `Qwen2Tokenizer` loaded from `CosyVoice/pretrained_models/Fun-CosyVoice3-0.5B/CosyVoice-BlankEN`.
- **Russian Sentence Splitter:** `razdel.sentenize(text)` (respects Russian abbreviations, initials, direct speech).
- **Block Target Size:** `60–80 tokens` (~150–220 characters).
- **Hard Minimum Size:** At least `35–40 tokens` per block. If a sentence is shorter, merge it with the adjacent sentence in the same paragraph.
- **Character Preservation Rules:**
  - Preserve letter `Ё` / `ё` (never replace with `Е` / `е`).
  - Preserve quotation marks (`«...»`, `“...”`), dashes (`—`, `–`), colons, and ellipses.
  - Never add trailing ellipses (`...`) automatically, as it injects unwanted trailing hesitation into the synthesized speech.

---

## 3. Audio Splicing & Post-Processing Specifications

### 3.1 Timing & Pauses
Master audiobook assembly must observe the following pauses:
- **Between sentences inside a paragraph:** `200 ms` digital silence (`np.zeros(int(0.20 * 24000))`).
- **Between paragraphs:** `500 ms` digital silence (`np.zeros(int(0.50 * 24000))`).
- **Between chapter heading / arc title and story:** `500–700 ms` digital silence.
- **Master Audio End Tail:** ALWAYS append `500 ms` digital silence at the very end of the master audio file.
  > *Why:* The LAME MP3 encoder and hardware media players trim or flush buffer tails; without a 500 ms digital silence tail, the last spoken syllable (e.g. "...Дадли") will be clipped off.

### 3.2 Splice & Remontage Best Practices
When replacing or remontaging phrases in an existing audio file:
1. Run Whisper with `word_timestamps=True` to locate exact speech boundaries.
2. Analyze RMS energy to find the true acoustic silence window (`rms < 0.002`).
3. Apply `10 ms` linear or cosine fade-out on the preceding slice and `10 ms` fade-in on the subsequent slice to prevent DC offset clicks.

---

## 4. Environment & Execution Context

### 4.1 Python Environment & Paths
In the Windows environment for this repository:
```powershell
# Correct Python executable:
E:\AI-Dubbing\cosyvoice_env\python.exe

# Mandatory sys.path additions before importing cosyvoice:
import sys
sys.path.insert(0, r"E:\AI-Dubbing")
sys.path.insert(0, r"E:\AI-Dubbing\CosyVoice")
sys.path.insert(0, r"E:\AI-Dubbing\CosyVoice\third_party\Matcha-TTS")
```

### 4.2 Network & Telegram Notifications
In Russian network environments with DPI blocks on `api.telegram.org`:
- Do **NOT** make unproxied HTTP calls to Telegram.
- Use the active local proxy: `http://127.0.0.1:1372` via `urllib.request.ProxyHandler({"https": "http://127.0.0.1:1372", "http": "http://127.0.0.1:1372"})`.
- If the user specifies *"пока ничего в телеграм не отправляй"*, respect this directive and do NOT trigger Telegram uploads.

### 4.3 Automated Verification Checklist
Before reporting a synthesized audio task as completed:
1. Verify segment files exist on disk and have non-zero file sizes (`> 50 KB`).
2. Run Whisper on the first and last synthesized segments to confirm no words or endings were truncated.
3. Ensure the master WAV file is generated at `24000 Hz` and encoded to MP3 (`128 kbps` for standard, `48 kbps` mono for compact distribution).
