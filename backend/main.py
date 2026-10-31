import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel
from pydantic import BaseModel


# ============================================================
# EchoVault
# ============================================================

app = FastAPI(
    title="EchoVault API",
    description="Local-first family memory preservation API",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Local AI configuration
# ============================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434/api/generate",
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:3b",
)

WHISPER_MODEL_NAME = os.getenv(
    "WHISPER_MODEL",
    "base.en",
)

NOT_FOUND = "That detail isn't present in this memory."


# ============================================================
# Whisper
# ============================================================

print("Loading EchoVault transcription model...")

whisper_model = WhisperModel(
    WHISPER_MODEL_NAME,
    device="cpu",
    compute_type="int8",
)

print("EchoVault transcription model ready.")


# ============================================================
# Request models
# ============================================================

class ExtractMemoryRequest(BaseModel):
    story: str


class AskMemoryRequest(BaseModel):
    question: str

    story: Optional[str] = None
    transcript: Optional[str] = None
    original_transcript: Optional[str] = None
    originalTranscript: Optional[str] = None

    memory: Optional[Dict[str, Any]] = None
    memory_data: Optional[Dict[str, Any]] = None
    memoryData: Optional[Dict[str, Any]] = None


# ============================================================
# Basic helpers
# ============================================================

def normalize_space(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        value or "",
    ).strip()


def split_sentences(text: str) -> List[str]:
    text = text.strip()

    if not text:
        return []

    pieces = re.split(
        r"(?<=[.!?])\s+|\n+",
        text,
    )

    return [
        piece.strip()
        for piece in pieces
        if piece.strip()
    ]


# ============================================================
# Fast Ollama call
# ============================================================

def ollama_generate(
    prompt: str,
    num_predict: int = 120,
    timeout: int = 90,
) -> str:

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,

                "prompt": prompt,

                "stream": False,

                # Keep Qwen loaded in memory so later questions
                # are much faster.
                "keep_alive": "30m",

                # Ask Ollama to return structured JSON.
                "format": "json",

                "options": {
                    "temperature": 0,

                    # We only need short answers.
                    "num_predict": num_predict,

                    # Enough context for a normal family memory,
                    # without unnecessarily slowing down Qwen.
                    "num_ctx": 2048,
                },
            },
            timeout=timeout,
        )

        response.raise_for_status()

        data = response.json()

        return normalize_space(
            data.get("response", "")
        )

    except requests.RequestException as exc:

        raise HTTPException(
            status_code=503,
            detail=(
                "Qwen is not available. "
                "Make sure Ollama is running."
            ),
        ) from exc


def parse_json_object(
    raw_text: str,
) -> Dict[str, Any]:

    if not raw_text:
        return {}

    cleaned = raw_text.strip()

    cleaned = cleaned.replace(
        "```json",
        "",
    )

    cleaned = cleaned.replace(
        "```",
        "",
    )

    cleaned = cleaned.strip()

    try:
        parsed = json.loads(
            cleaned
        )

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    match = re.search(
        r"\{.*\}",
        cleaned,
        re.DOTALL,
    )

    if match:

        try:
            parsed = json.loads(
                match.group(0)
            )

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

    return {}


# ============================================================
# Evidence verification
# ============================================================

def verify_evidence(
    evidence: str,
    transcript: str,
) -> str:

    evidence = normalize_space(
        evidence
    )

    if not evidence:
        return ""

    evidence_lower = evidence.lower()

    sentences = split_sentences(
        transcript
    )

    # Exact sentence match
    for sentence in sentences:

        if (
            normalize_space(sentence).lower()
            == evidence_lower
        ):
            return sentence

    # Evidence appears inside original sentence
    for sentence in sentences:

        sentence_lower = normalize_space(
            sentence
        ).lower()

        if evidence_lower in sentence_lower:
            return sentence

    # Approximate matching
    evidence_words = {
        word
        for word in re.findall(
            r"[a-z0-9']+",
            evidence_lower,
        )
        if len(word) > 2
    }

    if not evidence_words:
        return ""

    best_sentence = ""
    best_score = 0.0

    for sentence in sentences:

        sentence_words = {
            word
            for word in re.findall(
                r"[a-z0-9']+",
                sentence.lower(),
            )
            if len(word) > 2
        }

        if not sentence_words:
            continue

        overlap = len(
            evidence_words
            & sentence_words
        )

        score = overlap / max(
            len(evidence_words),
            1,
        )

        if score > best_score:

            best_score = score
            best_sentence = sentence

    if best_score >= 0.60:
        return best_sentence

    return ""


def find_sentence_containing(
    value: str,
    transcript: str,
) -> str:

    value = normalize_space(
        value
    ).lower()

    if not value:
        return ""

    for sentence in split_sentences(
        transcript
    ):

        if value in sentence.lower():
            return sentence

    return ""


# ============================================================
# Memory extraction verification
# ============================================================

def verify_items(
    items: Any,
    transcript: str,
) -> List[Dict[str, str]]:

    verified = []

    if not isinstance(items, list):
        return verified

    for item in items:

        if not isinstance(item, dict):
            continue

        name = normalize_space(
            str(
                item.get("name")
                or ""
            )
        )

        evidence = normalize_space(
            str(
                item.get("evidence")
                or ""
            )
        )

        if not name:
            continue

        verified_evidence = verify_evidence(
            evidence,
            transcript,
        )

        if not verified_evidence:

            verified_evidence = (
                find_sentence_containing(
                    name,
                    transcript,
                )
            )

        if not verified_evidence:
            continue

        verified.append(
            {
                "name": name,
                "evidence": verified_evidence,
            }
        )

    return verified


def verify_moments(
    moments: Any,
    transcript: str,
) -> List[Dict[str, str]]:

    verified = []

    if not isinstance(moments, list):
        return verified

    for item in moments:

        if not isinstance(item, dict):
            continue

        year = normalize_space(
            str(
                item.get("year")
                or ""
            )
        )

        title = normalize_space(
            str(
                item.get("title")
                or "Memory"
            )
        )

        text = normalize_space(
            str(
                item.get("text")
                or ""
            )
        )

        evidence = normalize_space(
            str(
                item.get("evidence")
                or ""
            )
        )

        verified_evidence = verify_evidence(
            evidence,
            transcript,
        )

        if not verified_evidence and text:

            verified_evidence = verify_evidence(
                text,
                transcript,
            )

        if not verified_evidence:
            continue

        verified.append(
            {
                "year": year,
                "title": title,
                "text": (
                    text
                    or verified_evidence
                ),
                "evidence": verified_evidence,
            }
        )

    return verified


# ============================================================
# Find original transcript from frontend request
# ============================================================

def get_transcript(
    request: AskMemoryRequest,
) -> str:

    candidates = [
        request.story,
        request.transcript,
        request.original_transcript,
        request.originalTranscript,
    ]

    for candidate in candidates:

        if (
            isinstance(candidate, str)
            and candidate.strip()
        ):
            return candidate.strip()

    memory_objects = [
        request.memory,
        request.memory_data,
        request.memoryData,
    ]

    transcript_keys = [
        "originalTranscript",
        "original_transcript",
        "transcript",
        "story",
        "sourceText",
        "source",
    ]

    for memory in memory_objects:

        if not isinstance(
            memory,
            dict,
        ):
            continue

        for key in transcript_keys:

            value = memory.get(
                key
            )

            if (
                isinstance(value, str)
                and value.strip()
            ):
                return value.strip()

    return ""


# ============================================================
# FAST deterministic question handling
# ============================================================

def fast_question_answer(
    question: str,
    transcript: str,
) -> Optional[Dict[str, Any]]:

    q = normalize_space(
        question
    ).lower()

    # --------------------------------------------------------
    # Speaker name
    # --------------------------------------------------------

    speaker_name_question = (
        (
            "name" in q
            and (
                "speaker" in q
                or "speaking" in q
                or "person speaking" in q
            )
        )
        or "who is speaking" in q
        or "who's speaking" in q
        or "who spoke" in q
    )

    if speaker_name_question:

        patterns = [
            r"\bthis is\s+([A-Za-z][A-Za-z.'-]{1,40})\b",
            r"\bmy name is\s+([A-Za-z][A-Za-z.'-]{1,40})\b",
            r"\bi am\s+([A-Za-z][A-Za-z.'-]{1,40})\b",
            r"\bi'm\s+([A-Za-z][A-Za-z.'-]{1,40})\b",
        ]

        for sentence in split_sentences(
            transcript
        ):

            for pattern in patterns:

                match = re.search(
                    pattern,
                    sentence,
                    re.IGNORECASE,
                )

                if match:

                    raw_name = (
                        match
                        .group(1)
                        .strip(".,!?;:")
                    )

                    if raw_name:

                        name = (
                            raw_name[0].upper()
                            + raw_name[1:]
                        )

                        return {
                            "answer": (
                                f"The speaker says their name is {name}."
                            ),
                            "evidence": sentence,
                            "found": True,
                        }

    return None


# ============================================================
# API routes
# ============================================================

@app.get("/")
def root():

    return {
        "message": (
            "EchoVault backend is running"
        )
    }


# ============================================================
# Transcription
# ============================================================

@app.post("/transcribe-audio")
async def transcribe_audio(
    file: UploadFile = File(...),
    hints: str = Form(""),
):

    suffix = Path(
        file.filename
        or "recording.wav"
    ).suffix

    if not suffix:
        suffix = ".wav"

    temp_path = ""

    try:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temp_file:

            temp_path = (
                temp_file.name
            )

            temp_file.write(
                await file.read()
            )

        prompt = (
            "Personal family memory spoken in Indian English. "
            "Preserve names, places, foods, dates and relationships."
        )

        if hints.strip():

            prompt += (
                " Possible names or places: "
                + hints.strip()
            )

        segments, info = (
            whisper_model.transcribe(
                temp_path,
                language="en",

                # Speed/accuracy compromise
                beam_size=2,
                best_of=2,

                vad_filter=True,

                vad_parameters={
                    "min_silence_duration_ms": 400
                },

                initial_prompt=prompt,

                hotwords=(
                    hints.strip()
                    if hints.strip()
                    else None
                ),

                condition_on_previous_text=True,

                temperature=0.0,
            )
        )

        transcript = normalize_space(
            " ".join(
                segment.text.strip()
                for segment in segments
                if segment.text.strip()
            )
        )

        if not transcript:

            raise HTTPException(
                status_code=422,
                detail=(
                    "No clear speech was detected."
                ),
            )

        return {
            "transcript": transcript,

            "language": getattr(
                info,
                "language",
                "en",
            ),

            "duration": getattr(
                info,
                "duration",
                None,
            ),
        }

    finally:

        if (
            temp_path
            and os.path.exists(
                temp_path
            )
        ):

            try:
                os.remove(
                    temp_path
                )

            except OSError:
                pass


# ============================================================
# Extract memory
# ============================================================

@app.post("/extract-memory")
def extract_memory(
    request: ExtractMemoryRequest,
):

    story = request.story.strip()

    if not story:

        raise HTTPException(
            status_code=400,
            detail="Memory is empty.",
        )

    prompt = f"""
You are EchoVault.

Read this family-memory transcript.

TRANSCRIPT:
\"\"\"
{story}
\"\"\"

Return JSON only:

{{
  "title": "short title",
  "summary": "short factual summary",
  "people": [
    {{
      "name": "name or relationship",
      "evidence": "exact transcript evidence"
    }}
  ],
  "places": [
    {{
      "name": "place",
      "evidence": "exact transcript evidence"
    }}
  ],
  "traditions": [
    {{
      "name": "tradition",
      "evidence": "exact transcript evidence"
    }}
  ],
  "moments": [
    {{
      "year": "",
      "title": "short title",
      "text": "short factual description",
      "evidence": "exact transcript evidence"
    }}
  ]
}}

Rules:
Use only the transcript.
Never invent information.
Keep evidence grounded in the transcript.
"""

    raw = ollama_generate(
        prompt,
        num_predict=420,
    )

    parsed = parse_json_object(
        raw
    )

    if not parsed:

        raise HTTPException(
            status_code=502,
            detail=(
                "Qwen did not return valid memory data."
            ),
        )

    return {
        "title": normalize_space(
            str(
                parsed.get("title")
                or "Preserved memory"
            )
        ),

        "summary": normalize_space(
            str(
                parsed.get("summary")
                or ""
            )
        ),

        "people": verify_items(
            parsed.get("people"),
            story,
        ),

        "places": verify_items(
            parsed.get("places"),
            story,
        ),

        "traditions": verify_items(
            parsed.get("traditions"),
            story,
        ),

        "moments": verify_moments(
            parsed.get("moments"),
            story,
        ),

        # Critical for Ask this memory
        "originalTranscript": story,
    }


# ============================================================
# Ask this memory
# ============================================================

@app.post("/ask-memory")
def ask_memory(
    request: AskMemoryRequest,
):

    question = normalize_space(
        request.question
    )

    if not question:

        raise HTTPException(
            status_code=400,
            detail="Question is empty.",
        )

    transcript = get_transcript(
        request
    )

    if not transcript:

        return {
            "answer": NOT_FOUND,
            "evidence": "",
            "found": False,
        }

    # --------------------------------------------------------
    # FAST PATH
    # No Qwen call for obvious questions.
    # --------------------------------------------------------

    fast_answer = fast_question_answer(
        question,
        transcript,
    )

    if fast_answer:
        return fast_answer

    # --------------------------------------------------------
    # Qwen path
    # --------------------------------------------------------

    prompt = f"""
You answer questions about ONE preserved family memory.

MEMORY:
{transcript}

QUESTION:
{question}

Rules:
- Use only the memory above.
- Do not use outside knowledge.
- Do not invent anything.
- If the answer is absent, use exactly:
  "{NOT_FOUND}"
- Keep the answer under 2 sentences.
- Give exact transcript evidence.

Return JSON only:

{{
  "answer": "...",
  "evidence": "..."
}}
"""

    raw = ollama_generate(
        prompt,

        # Short generation = faster
        num_predict=100,

        timeout=60,
    )

    parsed = parse_json_object(
        raw
    )

    answer = normalize_space(
        str(
            parsed.get("answer")
            or ""
        )
    )

    evidence = normalize_space(
        str(
            parsed.get("evidence")
            or ""
        )
    )

    if (
        not answer
        or NOT_FOUND.lower()
        in answer.lower()
    ):

        return {
            "answer": NOT_FOUND,
            "evidence": "",
            "found": False,
        }

    verified = verify_evidence(
        evidence,
        transcript,
    )

    # Try answer itself against transcript
    if not verified:

        verified = verify_evidence(
            answer,
            transcript,
        )

    # Search for answer keywords
    if not verified:

        keywords = [
            word.lower()
            for word in re.findall(
                r"[A-Za-z0-9'-]+",
                answer,
            )
            if len(word) >= 4
        ]

        best_sentence = ""
        best_hits = 0

        for sentence in split_sentences(
            transcript
        ):

            sentence_lower = (
                sentence.lower()
            )

            hits = sum(
                word in sentence_lower
                for word in keywords
            )

            if hits > best_hits:

                best_hits = hits
                best_sentence = sentence

        if best_hits:
            verified = best_sentence

    # Never allow an ungrounded answer
    if not verified:

        return {
            "answer": NOT_FOUND,
            "evidence": "",
            "found": False,
        }

    return {
        "answer": answer,
        "evidence": verified,
        "found": True,
    }