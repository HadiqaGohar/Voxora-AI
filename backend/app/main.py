import uuid
import time
import json
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List

from .database import init_db, log_interaction, add_feedback, get_analytics
from .tts import synthesize, synthesize_stream, list_voices, detect_language, auto_voice_for_text
from .chat import chat_completion, chat_completion_stream, check_ollama

app = FastAPI(title="Voxora AI Backend", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()


# --- Models ---

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    rate: Optional[str] = "+0%"
    pitch: Optional[str] = "+0Hz"
    auto_voice: Optional[bool] = False
    language: Optional[str] = None
    session_id: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = []
    language: Optional[str] = None
    model: Optional[str] = None
    session_id: Optional[str] = None
    voice: Optional[str] = None


class FeedbackRequest(BaseModel):
    interaction_id: int
    rating: int
    comment: Optional[str] = None


class STTLogRequest(BaseModel):
    text: str
    language: str
    session_id: Optional[str] = None
    latency_ms: Optional[float] = None


# --- TTS Endpoints ---

@app.get("/api/voices")
async def get_voices(language: Optional[str] = None):
    voices = await list_voices()
    if language:
        voices = [v for v in voices if v["Locale"].startswith(language)]
    return {"voices": voices, "count": len(voices)}


@app.get("/api/languages")
async def get_languages():
    voices = await list_voices()
    langs = {}
    for v in voices:
        locale = v["Locale"]
        lang_code = locale.split("-")[0]
        if lang_code not in langs:
            langs[lang_code] = {
                "code": lang_code,
                "name": v.get("LocaleName", locale).split(" ")[0],
                "locale": locale,
                "voice_count": 0,
            }
        langs[lang_code]["voice_count"] += 1
    return {"languages": list(langs.values()), "count": len(langs)}


@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(400, "Text cannot be empty")

    start = time.time()

    voice = req.voice
    if req.auto_voice or not voice:
        voice = await auto_voice_for_text(req.text)
        if not req.language:
            req.language = await detect_language(req.text)

    audio = await synthesize(req.text, voice=voice, rate=req.rate, pitch=req.pitch)
    latency = (time.time() - start) * 1000

    session_id = req.session_id or str(uuid.uuid4())
    log_interaction(
        session_id=session_id,
        type="tts",
        input_text=req.text[:500],
        language=req.language or voice.split("-")[0],
        voice=voice,
        latency_ms=latency,
    )

    return StreamingResponse(
        iter([audio]),
        media_type="audio/mpeg",
        headers={
            "X-Latency-Ms": str(round(latency)),
            "X-Voice": voice,
            "X-Language": req.language or voice.split("-")[0],
            "X-Session-Id": session_id,
        }
    )


@app.post("/api/tts/stream")
async def text_to_speech_stream(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(400, "Text cannot be empty")

    voice = req.voice
    if req.auto_voice or not voice:
        voice = await auto_voice_for_text(req.text)
        if not req.language:
            req.language = await detect_language(req.text)

    session_id = req.session_id or str(uuid.uuid4())

    async def generate():
        start = time.time()
        async for chunk in synthesize_stream(req.text, voice=voice, rate=req.rate, pitch=req.pitch):
            yield chunk
        latency = (time.time() - start) * 1000
        log_interaction(
            session_id=session_id,
            type="tts",
            input_text=req.text[:500],
            language=req.language or voice.split("-")[0],
            voice=voice,
            latency_ms=latency,
        )

    return StreamingResponse(
        generate(),
        media_type="audio/mpeg",
        headers={
            "X-Voice": voice,
            "X-Language": req.language or voice.split("-")[0],
            "X-Session-Id": session_id,
        }
    )


# --- Chat Endpoint ---

@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    start = time.time()
    lang = req.language
    if not lang:
        lang = await detect_language(req.message)

    messages = req.history + [{"role": "user", "content": req.message}]
    reply = await chat_completion(messages, model=req.model, language=lang)
    latency = (time.time() - start) * 1000

    session_id = req.session_id or str(uuid.uuid4())
    voice = req.voice or await auto_voice_for_text(reply)
    interaction_id = log_interaction(
        session_id=session_id,
        type="chat",
        input_text=req.message[:500],
        output_text=reply[:500],
        language=lang,
        voice=voice,
        latency_ms=latency,
    )

    return {
        "reply": reply,
        "language": lang,
        "voice": voice,
        "latency_ms": round(latency),
        "interaction_id": interaction_id,
        "session_id": session_id,
    }


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    lang = req.language
    if not lang:
        lang = await detect_language(req.message)

    messages = req.history + [{"role": "user", "content": req.message}]
    session_id = req.session_id or str(uuid.uuid4())

    async def generate():
        start = time.time()
        full_reply = ""
        async for token in chat_completion_stream(messages, model=req.model, language=lang):
            full_reply += token
            yield f"data: {json.dumps({'token': token})}\n\n"
        latency = (time.time() - start) * 1000
        voice = await auto_voice_for_text(full_reply)
        interaction_id = log_interaction(
            session_id=session_id,
            type="chat",
            input_text=req.message[:500],
            output_text=full_reply[:500],
            language=lang,
            voice=voice,
            latency_ms=latency,
        )
        yield f"data: {json.dumps({'done': True, 'interaction_id': interaction_id, 'voice': voice, 'latency_ms': round(latency)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# --- Voice Chat (STT → Chat → TTS combined) ---

@app.post("/api/voice-chat")
async def voice_chat(req: ChatRequest):
    """Full voice pipeline: text in → LLM reply → TTS audio out"""
    if not req.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    start = time.time()
    lang = req.language
    if not lang:
        lang = await detect_language(req.message)

    messages = req.history + [{"role": "user", "content": req.message}]
    reply = await chat_completion(messages, model=req.model, language=lang)
    chat_latency = (time.time() - start) * 1000

    voice = req.voice or await auto_voice_for_text(reply)
    tts_start = time.time()
    audio = await synthesize(reply, voice=voice)
    tts_latency = (time.time() - tts_start) * 1000

    session_id = req.session_id or str(uuid.uuid4())
    interaction_id = log_interaction(
        session_id=session_id,
        type="voice_chat",
        input_text=req.message[:500],
        output_text=reply[:500],
        language=lang,
        voice=voice,
        latency_ms=chat_latency + tts_latency,
    )

    return StreamingResponse(
        iter([audio]),
        media_type="audio/mpeg",
        headers={
            "X-Reply-Text": reply[:200],
            "X-Lang": lang,
            "X-Voice": voice,
            "X-Chat-Latency": str(round(chat_latency)),
            "X-TTS-Latency": str(round(tts_latency)),
            "X-Interaction-Id": str(interaction_id),
            "X-Session-Id": session_id,
        }
    )


# --- STT Logging ---

@app.post("/api/stt/log")
async def log_stt(req: STTLogRequest):
    session_id = req.session_id or str(uuid.uuid4())
    interaction_id = log_interaction(
        session_id=session_id,
        type="stt",
        input_text=req.text[:500],
        language=req.language,
        latency_ms=req.latency_ms,
    )
    return {"interaction_id": interaction_id, "session_id": session_id}


# --- Feedback ---

@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest):
    if req.rating not in (1, -1):
        raise HTTPException(400, "Rating must be 1 (thumbs up) or -1 (thumbs down)")
    add_feedback(req.interaction_id, req.rating, req.comment)
    return {"ok": True}


# --- Analytics ---

@app.get("/api/analytics")
async def analytics():
    return get_analytics()


@app.get("/api/health")
async def health():
    ollama_ok = await check_ollama()
    return {
        "status": "ok",
        "ollama": ollama_ok,
        "version": "2.0.0",
    }
