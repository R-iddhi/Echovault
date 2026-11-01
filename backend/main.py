import copy
import hashlib
import json
import os
import re
import tempfile
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel
from pydantic import BaseModel


# ============================================================
# EchoVault - faster local transcription and memory preservation
# ============================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434/api/generate",
)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "base.en")
NOT_FOUND = "That detail isn't present in this memory."

# Limit CPU threads so the laptop remains usable during transcription.
WHISPER_CPU_THREADS = min(os.cpu_count() or 4, 6)

# If the same transcript is preserved again in this backend session,
# return the verified result immediately instead of calling Qwen again.
EXTRACTION_CACHE_LIMIT = 10
EXTRACTION_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

print("EchoVault: loading Whisper model...")
whisper_model = WhisperModel(
    WHISPER_MODEL_NAME,
    device="cpu",
    compute_type="int8",
    cpu_threads=WHISPER_CPU_THREADS,
    num_workers=1,
)
print("EchoVault: Whisper model is ready.")


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
# Shared text helpers
# ============================================================

def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def split_sentences(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []

    return [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+|\n+", text)
        if part.strip()
    ]


def parse_json_object(raw_text: str) -> Dict[str, Any]:
    if not raw_text:
        return {}

    cleaned = raw_text.strip()

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return {}

    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


# ============================================================
# Qwen - warm model at backend startup and keep it loaded
# ============================================================

def qwen_request_payload(prompt: str, num_predict: int) -> Dict[str, Any]:
    return {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "30m",
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": num_predict,
            "num_ctx": 2048,
        },
    }


def warm_qwen() -> None:
    """Load Qwen before the user clicks Preserve for the first time."""
    try:
        response = requests.post(
            OLLAMA_URL,
            json=qwen_request_payload(
                '{"ready": true}',
                num_predict=8,
            ),
            timeout=(3, 90),
        )
        response.raise_for_status()
        print(f"EchoVault: {OLLAMA_MODEL} is loaded and ready.")
    except requests.RequestException as exc:
        # Do not prevent the app from starting if Ollama is not open yet.
        print(
            "EchoVault: Qwen warm-up could not run. "
            "Make sure Ollama is open. First Preserve may take longer. "
            f"Details: {exc}"
        )




def ollama_generate(
    prompt: str,
    num_predict: int = 120,
    timeout: int = 120,
) -> str:
    try:
        response = requests.post(
            OLLAMA_URL,
            json=qwen_request_payload(prompt, num_predict),
            timeout=(5, timeout),
        )
        response.raise_for_status()

        generated = str(
            response.json().get("response", "")
        ).strip()

        if not generated:
            raise HTTPException(
                status_code=502,
                detail="Qwen returned an empty response. Please try again.",
            )

        return generated

    except requests.Timeout as exc:
        raise HTTPException(
            status_code=504,
            detail="Qwen took too long to respond. Please try again.",
        ) from exc

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail="Qwen is not available. Make sure Ollama is running.",
        ) from exc


# ============================================================
# Evidence verification
# ============================================================

def verify_evidence(evidence: str, transcript: str) -> str:
    evidence = normalize_space(evidence)
    if not evidence:
        return ""

    evidence_lower = evidence.lower()
    sentences = split_sentences(transcript)

    # Exact sentence, then exact phrase inside an original sentence.
    for sentence in sentences:
        if normalize_space(sentence).lower() == evidence_lower:
            return sentence

    for sentence in sentences:
        if evidence_lower in normalize_space(sentence).lower():
            return sentence

    # Conservative fallback for small punctuation differences.
    evidence_words = {
        word
        for word in re.findall(r"[a-z0-9']+", evidence_lower)
        if len(word) > 2
    }
    if not evidence_words:
        return ""

    best_sentence = ""
    best_score = 0.0

    for sentence in sentences:
        sentence_words = {
            word
            for word in re.findall(r"[a-z0-9']+", sentence.lower())
            if len(word) > 2
        }
        if not sentence_words:
            continue

        score = len(evidence_words & sentence_words) / len(evidence_words)
        if score > best_score:
            best_score = score
            best_sentence = sentence

    return best_sentence if best_score >= 0.60 else ""


def find_sentence_containing(value: str, transcript: str) -> str:
    value = normalize_space(value).lower()
    if not value:
        return ""

    for sentence in split_sentences(transcript):
        if value in sentence.lower():
            return sentence

    return ""


def verify_items(
    items: Any,
    transcript: str,
    limit: int = 3,
) -> List[Dict[str, str]]:
    verified: List[Dict[str, str]] = []

    if not isinstance(items, list):
        return verified

    for item in items:
        if len(verified) >= limit:
            break
        if not isinstance(item, dict):
            continue

        name = normalize_space(str(item.get("name") or ""))
        evidence = normalize_space(str(item.get("evidence") or ""))
        if not name:
            continue

        source_sentence = verify_evidence(evidence, transcript)
        if not source_sentence:
            source_sentence = find_sentence_containing(name, transcript)

        if source_sentence:
            # Keep the exact {name, evidence} structure used by the frontend.
            verified.append({
                "name": name,
                "evidence": source_sentence,
            })

    return verified


def verify_moments(
    moments: Any,
    transcript: str,
    limit: int = 3,
) -> List[Dict[str, str]]:
    verified: List[Dict[str, str]] = []

    if not isinstance(moments, list):
        return verified

    for item in moments:
        if len(verified) >= limit:
            break
        if not isinstance(item, dict):
            continue

        year = normalize_space(str(item.get("year") or "Undated"))
        title = normalize_space(str(item.get("title") or "Memory"))
        description = normalize_space(str(item.get("text") or ""))
        evidence = normalize_space(str(item.get("evidence") or ""))

        source_sentence = verify_evidence(evidence, transcript)
        if not source_sentence and description:
            source_sentence = verify_evidence(description, transcript)

        if source_sentence:
            verified.append({
                "year": year or "Undated",
                "title": title or "Memory",
                "text": description or source_sentence,
                "evidence": source_sentence,
            })

    return verified


# ============================================================
# Ask this memory - retain original transcript
# ============================================================

def get_transcript(request: AskMemoryRequest) -> str:
    candidates = [
        request.story,
        request.transcript,
        request.original_transcript,
        request.originalTranscript,
    ]

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    transcript_keys = [
        "originalTranscript",
        "original_transcript",
        "transcript",
        "story",
        "sourceText",
        "source",
    ]

    for memory in [
        request.memory,
        request.memory_data,
        request.memoryData,
    ]:
        if not isinstance(memory, dict):
            continue

        for key in transcript_keys:
            value = memory.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def fast_question_answer(
    question: str,
    transcript: str,
) -> Optional[Dict[str, Any]]:
    q = normalize_space(question).lower()

    asks_speaker_name = (
        ("name" in q and ("speaker" in q or "speaking" in q))
        or "who is speaking" in q
        or "who's speaking" in q
        or "who spoke" in q
    )
    if not asks_speaker_name:
        return None

    patterns = [
        r"\bmy name is\s+([A-Za-z][A-Za-z.'-]{1,40})\b",
        r"\bthis is\s+([A-Za-z][A-Za-z.'-]{1,40})\b",
        r"\bi'm\s+([A-Za-z][A-Za-z.'-]{1,40})\b",
        r"\bi am\s+([A-Za-z][A-Za-z.'-]{1,40})\b",
    ]
    stop_words = {
        "a", "an", "the", "student", "person", "here", "speaking",
    }

    for sentence in split_sentences(transcript):
        for pattern in patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if not match:
                continue

            raw_name = match.group(1).strip(".,!?;:")
            if not raw_name or raw_name.lower() in stop_words:
                continue

            name = raw_name[0].upper() + raw_name[1:]
            return {
                "answer": f"The speaker says their name is {name}.",
                "evidence": sentence,
                "found": True,
                "grounded": True,
            }

    return None


# ============================================================
# Whisper - CPU-friendly transcription
# ============================================================

def transcribe_file(
    temp_path: str,
    hints: str,
) -> Dict[str, Any]:
    prompt = (
        "Personal family memory spoken in Indian English. "
        "Preserve names, places, foods, dates and relationships."
    )
    if hints.strip():
        prompt += " Possible names or places: " + hints.strip()

    segments, info = whisper_model.transcribe(
        temp_path,
        language="en",
        beam_size=1,
        vad_filter=True,
        vad_parameters={
            "min_silence_duration_ms": 500,
        },
        initial_prompt=prompt,
        hotwords=hints.strip() if hints.strip() else None,
        condition_on_previous_text=False,
        temperature=0.0,
    )

    transcript = normalize_space(
        " ".join(
            segment.text.strip()
            for segment in segments
            if segment.text.strip()
        )
    )

    return {
        "transcript": transcript,
        "language": getattr(info, "language", "en"),
        "duration": getattr(info, "duration", None),
    }


# ============================================================
# FastAPI application
# ============================================================

app = FastAPI(
    title="EchoVault API",
    description="Local-first family memory preservation API",
    version="1.2.0",
)


@app.on_event("startup")
def startup_warm_qwen() -> None:
    # This runs when the backend starts, not when the user clicks Preserve.
    warm_qwen()


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


@app.get("/")
def root() -> Dict[str, str]:
    return {
        "message": "EchoVault backend is running",
        "whisper_model": WHISPER_MODEL_NAME,
        "ollama_model": OLLAMA_MODEL,
    }


# ============================================================
# Transcribe endpoint
# ============================================================

@app.post("/transcribe-audio")
async def transcribe_audio(
    file: UploadFile = File(...),
    hints: str = Form(""),
) -> Dict[str, Any]:
    allowed_extensions = {
        ".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg",
    }

    suffix = Path(file.filename or "recording.wav").suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported audio file. "
                "Use MP3, WAV, M4A, MP4, WEBM, or OGG."
            ),
        )

    temp_path = ""
    started = time.perf_counter()

    try:
        # Write in chunks to avoid loading a large recording entirely into RAM.
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temp_file:
            temp_path = temp_file.name
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                temp_file.write(chunk)

        if not temp_path or os.path.getsize(temp_path) == 0:
            raise HTTPException(
                status_code=400,
                detail="Audio file is empty.",
            )

        # faster-whisper is CPU-bound, so run it outside the async event loop.
        result = await __import__("starlette.concurrency", fromlist=["run_in_threadpool"]).run_in_threadpool(
            transcribe_file,
            temp_path,
            hints or "",
        )

        if not result["transcript"]:
            raise HTTPException(
                status_code=422,
                detail="No clear speech was detected in this recording.",
            )

        processing_seconds = round(time.perf_counter() - started, 2)
        print(
            "EchoVault: transcription completed in "
            f"{processing_seconds} seconds."
        )

        return {
            **result,
            "language_probability": None,
            "processing_seconds": processing_seconds,
        }

    except HTTPException:
        raise
    except Exception as exc:
        print(f"EchoVault transcription error: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Audio transcription failed: {exc}",
        ) from exc
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


# ============================================================
# Preserve endpoint - compact Qwen response + repeat cache
# ============================================================

@app.post("/extract-memory")
def extract_memory(
    request: ExtractMemoryRequest,
) -> Dict[str, Any]:
    story = request.story.strip()

    if len(story) < 30:
        raise HTTPException(
            status_code=400,
            detail="Please provide a little more of the original memory.",
        )

    started = time.perf_counter()
    cache_key = hashlib.sha256(
        story.encode("utf-8")
    ).hexdigest()

    # Re-preserving the exact same story during this backend session is instant.
    if cache_key in EXTRACTION_CACHE:
        EXTRACTION_CACHE.move_to_end(cache_key)
        cached = copy.deepcopy(EXTRACTION_CACHE[cache_key])
        cached["cached"] = True
        cached["processing_seconds"] = round(
            time.perf_counter() - started,
            3,
        )
        print("EchoVault: returned cached preservation result.")
        return cached

    prompt = f'''
You are EchoVault, a careful family-memory preservation assistant.

Read the transcript and extract only details explicitly stated in it.

TRANSCRIPT:
"""
{story}
"""

Return one valid JSON object with exactly these keys:
{{
  "title": "short memory title",
  "summary": "one short factual sentence",
  "people": [{{"name": "person name or stated relationship", "evidence": "exact supporting transcript sentence"}}],
  "places": [{{"name": "place name", "evidence": "exact supporting transcript sentence"}}],
  "traditions": [{{"name": "tradition or repeated practice", "evidence": "exact supporting transcript sentence"}}],
  "moments": [{{"year": "year or Undated", "title": "short title", "text": "short factual description", "evidence": "exact supporting transcript sentence"}}]
}}

Rules:
- Use only the transcript. Never use outside knowledge.
- Never invent a name, person, place, year, relationship, tradition or event.
- Evidence must be copied exactly from the transcript.
- Include no more than 3 people, 3 places, 3 traditions and 3 moments.
- Keep titles and descriptions short.
- Use empty arrays for categories not mentioned.
- Do not repeat an item.
- Return JSON only.
'''

    raw = ollama_generate(
        prompt,
        num_predict=320,
        timeout=150,
    )
    parsed = parse_json_object(raw)

    if not parsed:
        raise HTTPException(
            status_code=502,
            detail="Qwen did not return valid memory data. Please try again.",
        )

    result: Dict[str, Any] = {
        "title": normalize_space(
            str(parsed.get("title") or "Preserved memory")
        ),
        "summary": normalize_space(
            str(parsed.get("summary") or "")
        ),
        "people": verify_items(
            parsed.get("people"),
            story,
            limit=3,
        ),
        "places": verify_items(
            parsed.get("places"),
            story,
            limit=3,
        ),
        "traditions": verify_items(
            parsed.get("traditions"),
            story,
            limit=3,
        ),
        "moments": verify_moments(
            parsed.get("moments"),
            story,
            limit=3,
        ),
        "originalTranscript": story,
    }

    EXTRACTION_CACHE[cache_key] = copy.deepcopy(result)
    EXTRACTION_CACHE.move_to_end(cache_key)
    while len(EXTRACTION_CACHE) > EXTRACTION_CACHE_LIMIT:
        EXTRACTION_CACHE.popitem(last=False)

    result["cached"] = False
    result["processing_seconds"] = round(
        time.perf_counter() - started,
        2,
    )
    print(
        "EchoVault: preservation completed in "
        f"{result['processing_seconds']} seconds."
    )
    return result


# ============================================================
# Ask endpoint - original-transcript grounding retained
# ============================================================

@app.post("/ask-memory")
def ask_memory(
    request: AskMemoryRequest,
) -> Dict[str, Any]:
    question = normalize_space(request.question)

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question is empty.",
        )

    transcript = get_transcript(request)
    if not transcript:
        return {
            "answer": NOT_FOUND,
            "evidence": "",
            "found": False,
            "grounded": False,
        }

    # Speaker-name questions are answered directly without calling Qwen.
    fast_answer = fast_question_answer(question, transcript)
    if fast_answer:
        return fast_answer

    prompt = f'''
Answer the question using ONLY this preserved family-memory transcript.

TRANSCRIPT:
"""
{transcript}
"""

QUESTION: {question}

Rules:
- Do not use outside knowledge.
- Do not guess or invent anything.
- If the detail is absent, answer exactly: {NOT_FOUND}
- Keep the answer to one short sentence.
- Evidence must be one exact sentence copied from the transcript.

Return JSON only:
{{"answer": "...", "evidence": "..."}}
'''

    raw = ollama_generate(
        prompt,
        num_predict=100,
        timeout=60,
    )
    parsed = parse_json_object(raw)

    answer = normalize_space(str(parsed.get("answer") or ""))
    evidence = normalize_space(str(parsed.get("evidence") or ""))

    if not answer or NOT_FOUND.lower() in answer.lower():
        return {
            "answer": NOT_FOUND,
            "evidence": "",
            "found": False,
            "grounded": False,
        }

    verified = verify_evidence(evidence, transcript)
    if not verified:
        verified = verify_evidence(answer, transcript)

    # Reject answers which cannot be tied to the original transcript.
    if not verified:
        return {
            "answer": NOT_FOUND,
            "evidence": "",
            "found": False,
            "grounded": False,
        }

    return {
        "answer": answer,
        "evidence": verified,
        "found": True,
        "grounded": True,
    }
