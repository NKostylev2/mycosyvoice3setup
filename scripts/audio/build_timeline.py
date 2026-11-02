from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional


PROJECT_ROOT = Path(r"E:\AI-Dubbing")
EPISODE = "S01E01"

WORK = PROJECT_ROOT / "work" / EPISODE

SRT_JSON = WORK / "normalized_subtitles.json"
VAD_JSON = WORK / "audio" / "vad.json"
WHISPER_JSON = WORK / "whisperx" / "source.json"

TIMELINE_JSON = WORK / "timeline.json"
REPORT_JSON = WORK / "timeline_report.json"


# =====================================================================
# CONFIG
# =====================================================================

@dataclass
class Config:
    # SRT clustering
    max_cluster_gap: float = 0.35
    max_cluster_duration: float = 12.0

    # Matching
    max_whisper_segments_per_cluster: int = 4
    max_time_distance: float = 20.0

    # Scores
    strong_score: float = 0.72
    high_score: float = 0.52
    review_score: float = 0.34

    # Text matching
    remove_fillers: bool = False


CFG = Config()


# =====================================================================
# DATA CLASSES
# =====================================================================

@dataclass
class SubtitleEvent:
    id: str
    start: float
    end: float
    text: str

    speaker: Optional[str] = None
    classification: str = "DIALOGUE"

    source_index: int = -1

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class SRTCluster:
    cluster_id: int
    events: list[SubtitleEvent]

    start: float
    end: float
    text: str

    @property
    def event_ids(self) -> list[str]:
        return [event.id for event in self.events]


@dataclass
class WhisperWord:
    word: str
    start: float
    end: float
    score: Optional[float] = None


@dataclass
class WhisperSegment:
    index: int
    start: float
    end: float
    text: str

    words: list[WhisperWord] = field(default_factory=list)
    speaker: Optional[str] = None

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class MatchCandidate:
    start_index: int
    end_index: int

    score: float
    text_score: float
    time_score: float

    text: str


# =====================================================================
# JSON
# =====================================================================

def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# =====================================================================
# TEXT
# =====================================================================

TAG_RE = re.compile(r"<[^>]+>")
ASS_TAG_RE = re.compile(r"\{\\[^}]+\}")

NON_DIALOGUE_RE = re.compile(
    r"""
    ^
    \s*
    (?:
        \[[^\]]+\]
        |
        \([^)]+\)
        |
        <[^>]+>
        |
        ♪.*?♪
        |
        (?:music|applause|laughter|laughs|sighs|screams?|"
        r"crying|cheering|crowd|footsteps?|door opens|door closes|"
        r"phone rings?|ringing|silence|inaudible)"
    )
    \s*
    $
    """,
    re.IGNORECASE | re.VERBOSE,
)


def clean_markup(text: str) -> str:
    text = text or ""

    text = TAG_RE.sub(" ", text)
    text = ASS_TAG_RE.sub(" ", text)

    text = text.replace("\\N", " ")
    text = text.replace("\\n", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_text(text: str) -> str:
    text = clean_markup(text)

    text = text.lower()
    text = text.replace("’", "'")

    # English matching only.
    text = re.sub(r"[^a-z0-9']+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def tokenize(text: str) -> list[str]:
    return normalize_text(text).split()


def text_similarity(a: str, b: str) -> float:
    """
    Text similarity designed for subtitle fragments.

    Uses:
      - sequence similarity
      - token overlap
      - longest common contiguous block

    This is intentionally symmetric.
    """

    ta = tokenize(a)
    tb = tokenize(b)

    if not ta or not tb:
        return 0.0

    sequence_score = SequenceMatcher(
        None,
        ta,
        tb,
    ).ratio()

    sa = set(ta)
    sb = set(tb)

    token_overlap = (
        len(sa & sb) / len(sa | sb)
        if sa and sb
        else 0.0
    )

    matcher = SequenceMatcher(
        None,
        ta,
        tb,
    )

    match = matcher.find_longest_match(
        0,
        len(ta),
        0,
        len(tb),
    )

    longest_block = match.size / max(
        1,
        min(len(ta), len(tb)),
    )

    return (
        sequence_score * 0.50
        + token_overlap * 0.25
        + longest_block * 0.25
    )


# =====================================================================
# CLASSIFICATION
# =====================================================================

def classify_srt_text(text: str) -> str:
    clean = clean_markup(text)

    if not clean:
        return "NON_DIALOGUE"

    if NON_DIALOGUE_RE.match(clean):
        return "NON_DIALOGUE"

    # Music notation.
    stripped = clean.strip("♪ ")
    if not stripped:
        return "NON_DIALOGUE"

    return "DIALOGUE"


# =====================================================================
# SRT INPUT
# =====================================================================

def get_srt_entries(data: Any) -> list[dict]:
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        raise ValueError(
            "normalized_subtitles.json has unsupported structure"
        )

    for key in (
        "entries",
        "subtitles",
        "items",
        "segments",
        "records",
    ):
        value = data.get(key)

        if isinstance(value, list):
            return value

    raise ValueError(
        "Cannot find subtitle entries in normalized_subtitles.json"
    )


def parse_srt_events(data: Any) -> list[SubtitleEvent]:
    raw_entries = get_srt_entries(data)

    result: list[SubtitleEvent] = []

    for index, item in enumerate(raw_entries):

        source = item.get("source", {})

        start = item.get("start")
        end = item.get("end")

        if start is None:
            start = source.get("start")

        if end is None:
            end = source.get("end")

        if start is None or end is None:
            continue

        text = (
            item.get("text")
            or item.get("text_en")
            or source.get("text")
            or ""
        )

        text = clean_markup(str(text))

        speaker = (
            item.get("speaker")
            or source.get("speaker")
        )

        event_id = (
            item.get("id")
            or item.get("dialogue_id")
            or f"D{index + 1:04d}"
        )

        classification = (
            item.get("classification")
            or classify_srt_text(text)
        )

        result.append(
            SubtitleEvent(
                id=str(event_id),

                start=float(start),
                end=float(end),

                text=text,

                speaker=speaker,
                classification=classification,

                source_index=index,
            )
        )

    result.sort(
        key=lambda x: (
            x.start,
            x.end,
            x.source_index,
        )
    )

    return result


# =====================================================================
# SRT CLUSTERING
# =====================================================================

def make_cluster(
    cluster_id: int,
    events: list[SubtitleEvent],
) -> SRTCluster:

    text_parts = []

    for event in events:
        if event.text.strip():
            text_parts.append(event.text.strip())

    return SRTCluster(
        cluster_id=cluster_id,

        events=list(events),

        start=min(
            event.start
            for event in events
        ),

        end=max(
            event.end
            for event in events
        ),

        text=" ".join(text_parts),
    )


def cluster_srt(
    events: list[SubtitleEvent],
) -> list[SRTCluster]:

    dialogue = [
        event
        for event in events
        if event.classification == "DIALOGUE"
    ]

    if not dialogue:
        return []

    clusters: list[SRTCluster] = []

    current = [dialogue[0]]

    for event in dialogue[1:]:

        current_start = current[0].start

        current_end = max(
            item.end
            for item in current
        )

        current_duration = (
            current_end
            - current_start
        )

        overlaps = (
            event.start
            <= current_end
        )

        close = (
            event.start
            <= current_end
            + CFG.max_cluster_gap
        )

        previous_text = current[-1].text.strip()

        previous_has_terminal_punctuation = bool(
            re.search(
                r"[.!?…]$",
                previous_text,
            )
        )

        continuation = (
            not previous_has_terminal_punctuation
        )

        can_join = (
            current_duration
            <= CFG.max_cluster_duration
            and (
                overlaps
                or (
                    close
                    and continuation
                )
            )
        )

        if can_join:
            current.append(event)
        else:
            clusters.append(
                make_cluster(
                    len(clusters),
                    current,
                )
            )

            current = [event]

    clusters.append(
        make_cluster(
            len(clusters),
            current,
        )
    )

    return clusters


# =====================================================================
# VAD
# =====================================================================

def get_vad_intervals(data: Any) -> list[dict]:
    if isinstance(data, list):
        raw = data

    elif isinstance(data, dict):
        raw = (
            data.get("speech_intervals")
            or data.get("intervals")
            or data.get("segments")
            or data.get("speech_timestamps")
        )

    else:
        raw = None

    if not isinstance(raw, list):
        raise ValueError(
            "Cannot find VAD intervals in vad.json"
        )

    result = []

    for item in raw:

        start = item.get("start")
        end = item.get("end")

        if start is None or end is None:
            continue

        result.append(
            {
                "start": float(start),
                "end": float(end),
            }
        )

    return result


# =====================================================================
# WHISPERX
# =====================================================================

def get_whisper_segments(
    data: Any,
) -> list[WhisperSegment]:

    if not isinstance(data, dict):
        raise ValueError(
            "WhisperX JSON must be an object"
        )

    segments = data.get("segments")

    if not isinstance(segments, list):
        raise ValueError(
            "Cannot find WhisperX segments"
        )

    result = []

    for index, item in enumerate(segments):

        start = item.get("start")
        end = item.get("end")

        if start is None or end is None:
            continue

        text = str(
            item.get("text", "")
        ).strip()

        words = []

        for word in item.get("words", []):

            if (
                word.get("start") is None
                or word.get("end") is None
            ):
                continue

            score = word.get("score")

            if score is not None:
                try:
                    score = float(score)
                except (
                    TypeError,
                    ValueError,
                ):
                    score = None

            words.append(
                WhisperWord(
                    word=str(
                        word.get("word", "")
                    ).strip(),

                    start=float(
                        word["start"]
                    ),

                    end=float(
                        word["end"]
                    ),

                    score=score,
                )
            )

        result.append(
            WhisperSegment(
                index=index,

                start=float(start),
                end=float(end),

                text=text,

                words=words,

                speaker=item.get("speaker"),
            )
        )

    result.sort(
        key=lambda x: (
            x.start,
            x.end,
            x.index,
        )
    )

    return result


# =====================================================================
# INTERVAL MATH
# =====================================================================

def overlap(
    a_start: float,
    a_end: float,
    b_start: float,
    b_end: float,
) -> float:

    return max(
        0.0,
        min(
            a_end,
            b_end,
        )
        - max(
            a_start,
            b_start,
        ),
    )


def interval_iou(
    a_start: float,
    a_end: float,
    b_start: float,
    b_end: float,
) -> float:

    intersection = overlap(
        a_start,
        a_end,
        b_start,
        b_end,
    )

    union = (
        max(a_end, b_end)
        - min(a_start, b_start)
    )

    if union <= 0:
        return 0.0

    return intersection / union


def temporal_score(
    cluster: SRTCluster,
    start_segment: WhisperSegment,
    end_segment: WhisperSegment,
) -> float:

    ws = start_segment.start
    we = end_segment.end

    ov = overlap(
        cluster.start,
        cluster.end,
        ws,
        we,
    )

    if ov > 0:
        iou = interval_iou(
            cluster.start,
            cluster.end,
            ws,
            we,
        )

        return min(
            1.0,
            0.55 + 0.45 * iou,
        )

    if we < cluster.start:
        distance = cluster.start - we

    else:
        distance = ws - cluster.end

    return math.exp(
        -distance / 4.0
    )


# =====================================================================
# WHISPER CANDIDATE GENERATION
# =====================================================================

def build_candidate_text(
    segments: list[WhisperSegment],
) -> str:

    return " ".join(
        segment.text.strip()
        for segment in segments
        if segment.text.strip()
    )


def choose_whisper_candidate(
    cluster: SRTCluster,
    whisper_segments: list[WhisperSegment],
    pointer: int,
) -> Optional[MatchCandidate]:
    """
    Global sequential matcher.

    IMPORTANT:
    `pointer` can only move forward.

    Therefore:
        SRT cluster N
        cannot match Whisper segment earlier
        than the segment used by cluster N-1.
    """

    if pointer >= len(whisper_segments):
        return None

    search_end = min(
        len(whisper_segments),
        pointer
        + 10
        + CFG.max_whisper_segments_per_cluster,
    )

    possible_starts = []

    for start_index in range(
        pointer,
        search_end,
    ):

        segment = whisper_segments[start_index]

        if (
            segment.start
            > cluster.end
            + CFG.max_time_distance
        ):
            break

        if (
            segment.end
            < cluster.start
            - CFG.max_time_distance
        ):
            continue

        possible_starts.append(
            start_index
        )

    if not possible_starts:
        return None

    best: Optional[MatchCandidate] = None

    for start_index in possible_starts:

        for length in range(
            1,
            CFG.max_whisper_segments_per_cluster + 1,
        ):

            end_index = (
                start_index
                + length
                - 1
            )

            if end_index >= len(
                whisper_segments
            ):
                break

            selected = whisper_segments[
                start_index:
                end_index + 1
            ]

            candidate_text = (
                build_candidate_text(
                    selected
                )
            )

            if not candidate_text:
                continue

            text_score = text_similarity(
                cluster.text,
                candidate_text,
            )

            time_score = temporal_score(
                cluster,
                selected[0],
                selected[-1],
            )

            score = (
                text_score * 0.78
                + time_score * 0.22
            )

            candidate = MatchCandidate(
                start_index=start_index,

                end_index=end_index,

                score=score,

                text_score=text_score,

                time_score=time_score,

                text=candidate_text,
            )

            if best is None:
                best = candidate
                continue

            if (
                candidate.score
                > best.score
            ):
                best = candidate

            elif (
                abs(
                    candidate.score
                    - best.score
                )
                < 0.02
            ):
                # For almost identical scores,
                # prefer the shorter Whisper span.
                candidate_length = (
                    candidate.end_index
                    - candidate.start_index
                )

                best_length = (
                    best.end_index
                    - best.start_index
                )

                if candidate_length < best_length:
                    best = candidate

    return best


# =====================================================================
# MATCH CLASS
# =====================================================================

def classify_match(
    candidate: Optional[MatchCandidate],
) -> str:

    if candidate is None:
        return "NO_MATCH"

    if (
        candidate.score
        >= CFG.strong_score
        and candidate.text_score
        >= 0.72
    ):
        return "STRONG"

    if (
        candidate.score
        >= CFG.high_score
        and candidate.text_score
        >= 0.55
    ):
        return "HIGH"

    if (
        candidate.score
        >= CFG.review_score
    ):
        return "REVIEW"

    return "WEAK"


# =====================================================================
# WORD TIMESTAMPS
# =====================================================================

def derive_speech_bounds(
    whisper_segments: list[WhisperSegment],
    fallback_start: float,
    fallback_end: float,
) -> tuple[
    float,
    float,
    Optional[float],
]:

    words = []

    for segment in whisper_segments:
        words.extend(
            segment.words
        )

    valid_words = [
        word
        for word in words
        if word.end >= word.start
    ]

    if not valid_words:
        return (
            fallback_start,
            fallback_end,
            None,
        )

    probabilities = [
        word.score
        for word in valid_words
        if word.score is not None
    ]

    average_probability = (
        sum(probabilities)
        / len(probabilities)
        if probabilities
        else None
    )

    speech_start = min(
        word.start
        for word in valid_words
    )

    speech_end = max(
        word.end
        for word in valid_words
    )

    return (
        speech_start,
        speech_end,
        average_probability,
    )


# =====================================================================
# VAD HELPERS
# =====================================================================

def best_vad_for_interval(
    start: float,
    end: float,
    vad_intervals: list[dict],
) -> tuple[
    Optional[dict],
    float,
]:

    best = None
    best_overlap = 0.0

    for vad in vad_intervals:

        ov = overlap(
            start,
            end,
            vad["start"],
            vad["end"],
        )

        if ov > best_overlap:
            best_overlap = ov
            best = vad

    return best, best_overlap


# =====================================================================
# TIMELINE BUILDER
# =====================================================================

def main():

    print("=" * 70)
    print("BUILD TIMELINE v0.2")
    print("=" * 70)

    print(
        f"Episode : {EPISODE}"
    )

    print(
        f"Work    : {WORK}"
    )

    # --------------------------------------------------------------
    # LOAD
    # --------------------------------------------------------------

    srt_data = load_json(
        SRT_JSON
    )

    vad_data = load_json(
        VAD_JSON
    )

    whisper_data = load_json(
        WHISPER_JSON
    )

    srt_events = parse_srt_events(
        srt_data
    )

    vad_intervals = get_vad_intervals(
        vad_data
    )

    whisper_segments = get_whisper_segments(
        whisper_data
    )

    print(
        f"SRT events       : {len(srt_events)}"
    )

    print(
        f"VAD intervals     : {len(vad_intervals)}"
    )

    print(
        f"Whisper segments  : {len(whisper_segments)}"
    )

    # --------------------------------------------------------------
    # CLASSIFICATION
    # --------------------------------------------------------------

    dialogue_events = [
        event
        for event in srt_events
        if event.classification == "DIALOGUE"
    ]

    non_dialogue_events = [
        event
        for event in srt_events
        if event.classification != "DIALOGUE"
    ]

    print(
        f"Dialogue events   : {len(dialogue_events)}"
    )

    print(
        f"Non-dialogue      : {len(non_dialogue_events)}"
    )

    # --------------------------------------------------------------
    # CLUSTERING
    # --------------------------------------------------------------

    clusters = cluster_srt(
        srt_events
    )

    print(
        f"SRT clusters      : {len(clusters)}"
    )

    # --------------------------------------------------------------
    # GLOBAL SEQUENTIAL MATCH
    # --------------------------------------------------------------

    records = []

    report_clusters = []

    whisper_pointer = 0

    matched_whisper_indices = set()

    stats = {
        "STRONG": 0,
        "HIGH": 0,
        "REVIEW": 0,
        "WEAK": 0,
        "NO_MATCH": 0,
    }

    # --------------------------------------------------------------
    # NON-DIALOGUE
    # --------------------------------------------------------------

    for event in non_dialogue_events:

        vad, vad_overlap = (
            best_vad_for_interval(
                event.start,
                event.end,
                vad_intervals,
            )
        )

        records.append(
            {
                "dialogue_id": event.id,

                "source": {
                    "subtitle_index": (
                        event.source_index + 1
                    ),

                    "text": event.text,

                    "start": event.start,

                    "end": event.end,

                    "speaker": event.speaker,
                },

                "classification": (
                    "NON_DIALOGUE"
                ),

                "whisperx": None,

                "vad": {
                    "start": (
                        vad["start"]
                        if vad
                        else None
                    ),

                    "end": (
                        vad["end"]
                        if vad
                        else None
                    ),

                    "overlap": vad_overlap,
                },

                "matching": {
                    "classification": (
                        "NON_DIALOGUE"
                    ),

                    "score": 1.0,

                    "text_score": 0.0,

                    "time_score": 0.0,

                    "cluster_id": None,

                    "whisper_indices": [],
                },

                "speech": {
                    "start": None,
                    "end": None,
                    "duration": None,
                },

                "semantic": {
                    "character_id": None,
                    "translation_ru": None,
                    "translation_status": (
                        "pending"
                    ),
                },

                "tts": {
                    "text": None,
                    "start": None,
                    "end": None,
                    "status": "pending",
                },
            }
        )

    # --------------------------------------------------------------
    # DIALOGUE CLUSTERS
    # --------------------------------------------------------------

    for cluster in clusters:

        candidate = choose_whisper_candidate(
            cluster,
            whisper_segments,
            whisper_pointer,
        )

        classification = classify_match(
            candidate
        )

        stats[classification] += 1

        if candidate is None:

            selected = []

            whisper_indices = []

            speech_start = None
            speech_end = None
            average_probability = None

            whisper_text = None
            whisper_start = None
            whisper_end = None

        else:

            selected = whisper_segments[
                candidate.start_index:
                candidate.end_index + 1
            ]

            whisper_pointer = (
                candidate.end_index + 1
            )

            for segment in selected:
                matched_whisper_indices.add(
                    segment.index
                )

            whisper_indices = [
                segment.index
                for segment in selected
            ]

            (
                speech_start,
                speech_end,
                average_probability,
            ) = derive_speech_bounds(
                selected,
                selected[0].start,
                selected[-1].end,
            )

            whisper_text = (
                build_candidate_text(
                    selected
                )
            )

            whisper_start = (
                selected[0].start
            )

            whisper_end = (
                selected[-1].end
            )

        report_clusters.append(
            {
                "cluster_id": (
                    cluster.cluster_id
                ),

                "source_ids": (
                    cluster.event_ids
                ),

                "source_start": (
                    cluster.start
                ),

                "source_end": (
                    cluster.end
                ),

                "source_text": (
                    cluster.text
                ),

                "matched": (
                    candidate is not None
                ),

                "classification": (
                    classification
                ),

                "score": (
                    candidate.score
                    if candidate
                    else 0.0
                ),

                "text_score": (
                    candidate.text_score
                    if candidate
                    else 0.0
                ),

                "time_score": (
                    candidate.time_score
                    if candidate
                    else 0.0
                ),

                "whisper_indices": (
                    whisper_indices
                ),

                "whisper_start": (
                    whisper_start
                ),

                "whisper_end": (
                    whisper_end
                ),

                "whisper_text": (
                    whisper_text
                ),

                "speech_start": (
                    speech_start
                ),

                "speech_end": (
                    speech_end
                ),

                "word_probability": (
                    average_probability
                ),
            }
        )

        # ----------------------------------------------------------
        # One cluster can contain several SRT rows.
        # Each original row keeps its own source timing/text,
        # while pointing to the SAME acoustic match.
        # ----------------------------------------------------------

        for event in cluster.events:

            vad, vad_overlap = (
                best_vad_for_interval(
                    event.start,
                    event.end,
                    vad_intervals,
                )
            )

            record = {
                "dialogue_id": event.id,

                "source": {
                    "subtitle_index": (
                        event.source_index + 1
                    ),

                    "text": event.text,

                    "start": event.start,

                    "end": event.end,

                    "speaker": event.speaker,
                },

                "classification": (
                    "DIALOGUE"
                ),

                "whisperx": {
                    "segment_indices": (
                        whisper_indices
                    ),

                    "text": whisper_text,

                    "start": whisper_start,

                    "end": whisper_end,

                    "words": [
                        {
                            "word": word.word,

                            "start": word.start,

                            "end": word.end,

                            "score": word.score,
                        }

                        for segment in selected

                        for word in segment.words
                    ],

                    "segments": [
                        {
                            "index": segment.index,

                            "start": segment.start,

                            "end": segment.end,

                            "text": segment.text,

                            "speaker": (
                                segment.speaker
                            ),
                        }

                        for segment in selected
                    ],
                },

                "vad": {
                    "start": (
                        vad["start"]
                        if vad
                        else None
                    ),

                    "end": (
                        vad["end"]
                        if vad
                        else None
                    ),

                    "overlap": vad_overlap,
                },

                "matching": {
                    "classification": (
                        classification
                    ),

                    "score": (
                        candidate.score
                        if candidate
                        else 0.0
                    ),

                    "text_score": (
                        candidate.text_score
                        if candidate
                        else 0.0
                    ),

                    "time_score": (
                        candidate.time_score
                        if candidate
                        else 0.0
                    ),

                    "cluster_id": (
                        cluster.cluster_id
                    ),

                    "cluster_source_ids": (
                        cluster.event_ids
                    ),

                    "whisper_indices": (
                        whisper_indices
                    ),
                },

                "speech": {
                    "start": speech_start,

                    "end": speech_end,

                    "duration": (
                        speech_end
                        - speech_start
                        if speech_start is not None
                        and speech_end is not None
                        else None
                    ),

                    "avg_word_probability": (
                        average_probability
                    ),
                },

                "semantic": {
                    "character_id": None,

                    "translation_ru": None,

                    "translation_status": (
                        "pending"
                    ),
                },

                "tts": {
                    "text": None,

                    "start": None,

                    "end": None,

                    "status": "pending",
                },
            }

            records.append(record)

    # --------------------------------------------------------------
    # STABLE SOURCE ORDER
    # --------------------------------------------------------------

    source_order = {
        event.id: event.source_index
        for event in srt_events
    }

    records.sort(
        key=lambda record:
        source_order.get(
            record["dialogue_id"],
            10**9,
        )
    )

    # --------------------------------------------------------------
    # UNMATCHED WHISPER
    # --------------------------------------------------------------

    unmatched_whisper = [
        {
            "segment_index": segment.index,

            "start": segment.start,

            "end": segment.end,

            "text": segment.text,
        }

        for segment in whisper_segments

        if segment.index
        not in matched_whisper_indices
    ]

    # --------------------------------------------------------------
    # TIMELINE
    # --------------------------------------------------------------

    timeline = {
        "schema_version": "0.2",

        "episode": EPISODE,

        "matcher": {
            "name": (
                "global_sequential_cluster_matcher"
            ),

            "version": "0.2",
        },

        "source_of_truth": {
            "semantic": "translation_pending",

            "timing": (
                "WhisperX_word_timestamps"
            ),
        },

        "stats": {
            "srt_events": len(srt_events),

            "dialogue_events": (
                len(dialogue_events)
            ),

            "non_dialogue_events": (
                len(non_dialogue_events)
            ),

            "srt_clusters": len(clusters),

            "whisper_segments": (
                len(whisper_segments)
            ),

            "matched_clusters": (
                sum(
                    1
                    for item in report_clusters
                    if item["matched"]
                )
            ),

            "unmatched_clusters": (
                sum(
                    1
                    for item in report_clusters
                    if not item["matched"]
                )
            ),

            "unmatched_whisper_segments": (
                len(unmatched_whisper)
            ),

            "classification": stats,
        },

        "records": records,
    }

    # --------------------------------------------------------------
    # REPORT
    # --------------------------------------------------------------

    report = {
        "schema_version": "0.2",

        "episode": EPISODE,

        "algorithm": {
            "name": (
                "global_sequential_cluster_matcher"
            ),

            "version": "0.2",

            "max_cluster_gap": (
                CFG.max_cluster_gap
            ),

            "max_cluster_duration": (
                CFG.max_cluster_duration
            ),

            "max_whisper_segments_per_cluster": (
                CFG.max_whisper_segments_per_cluster
            ),

            "max_time_distance": (
                CFG.max_time_distance
            ),
        },

        "inputs": {
            "srt_events": len(srt_events),

            "vad_intervals": len(vad_intervals),

            "whisper_segments": (
                len(whisper_segments)
            ),
        },

        "matching": stats,

        "whisper": {
            "matched_segments": (
                len(matched_whisper_indices)
            ),

            "unmatched_segments": (
                len(unmatched_whisper)
            ),

            "unmatched": unmatched_whisper,
        },

        "clusters": report_clusters,

        "notes": [
            (
                "NON_DIALOGUE events are excluded "
                "from Whisper text matching."
            ),

            (
                "SRT dialogue fragments are clustered "
                "before matching."
            ),

            (
                "Matching is monotonic: the Whisper "
                "pointer never moves backwards."
            ),

            (
                "A single SRT cluster may consume "
                "multiple consecutive Whisper segments."
            ),

            (
                "Acoustic speech boundaries come from "
                "WhisperX word timestamps when available."
            ),

            (
                "Original SRT timing remains preserved "
                "separately from speech timing."
            ),
        ],
    }

    # --------------------------------------------------------------
    # WRITE
    # --------------------------------------------------------------

    TIMELINE_JSON.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with TIMELINE_JSON.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            timeline,
            f,
            ensure_ascii=False,
            indent=2,
        )

    with REPORT_JSON.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            report,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # --------------------------------------------------------------
    # CONSOLE
    # --------------------------------------------------------------

    print()
    print("=" * 70)
    print("RESULT")
    print("=" * 70)

    print(
        f"SRT events             : "
        f"{len(srt_events)}"
    )

    print(
        f"Dialogue events        : "
        f"{len(dialogue_events)}"
    )

    print(
        f"Non-dialogue events    : "
        f"{len(non_dialogue_events)}"
    )

    print(
        f"SRT clusters            : "
        f"{len(clusters)}"
    )

    print(
        f"Whisper segments        : "
        f"{len(whisper_segments)}"
    )

    print(
        f"Matched clusters        : "
        f"{timeline['stats']['matched_clusters']}"
    )

    print(
        f"Unmatched clusters      : "
        f"{timeline['stats']['unmatched_clusters']}"
    )

    print()

    print(
        "Classification:"
    )

    for key in (
        "STRONG",
        "HIGH",
        "REVIEW",
        "WEAK",
        "NO_MATCH",
    ):

        print(
            f"  {key:10}: "
            f"{stats[key]}"
        )

    print()

    print(
        f"Whisper matched         : "
        f"{len(matched_whisper_indices)}"
        f"/{len(whisper_segments)}"
    )

    print(
        f"Whisper unmatched       : "
        f"{len(unmatched_whisper)}"
    )

    print()

    print(
        f"Timeline : {TIMELINE_JSON}"
    )

    print(
        f"Report   : {REPORT_JSON}"
    )

    print()
    print("BUILD PASSED")


# =====================================================================
# ENTRY POINT
# =====================================================================

if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:
        print(
            "\nInterrupted.",
            file=sys.stderr,
        )

        sys.exit(130)

    except Exception as exc:

        print()
        print("BUILD FAILED")

        print(
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )

        sys.exit(1)