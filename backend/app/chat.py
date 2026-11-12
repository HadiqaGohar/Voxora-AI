import httpx
import json
import os
from typing import Optional, AsyncGenerator

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://pilotron-ollama:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:latest")

SYSTEM_PROMPT = """You are Voxora AI, a helpful voice assistant. You respond in the SAME LANGUAGE the user spoke. Keep responses concise and natural for voice interaction. If the user speaks Urdu, respond in Urdu. If Hindi, respond in Hindi. If English, respond in English. Match their language exactly."""


async def chat_completion(messages: list, model: str = None,
                         language: str = None) -> str:
    model = model or DEFAULT_MODEL

    system_msg = SYSTEM_PROMPT
    if language:
        lang_names = {
            "ur": "Urdu", "hi": "Hindi", "en": "English", "ar": "Arabic",
            "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese",
            "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "tr": "Turkish",
            "bn": "Bengali", "ru": "Russian", "it": "Italian", "nl": "Dutch",
            "pl": "Polish", "th": "Thai", "vi": "Vietnamese", "id": "Indonesian",
        }
        lang_name = lang_names.get(language, language)
        system_msg += f" The user is speaking {lang_name}. Respond in {lang_name}."

    full_messages = [{"role": "system", "content": system_msg}] + messages

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": full_messages,
                "stream": False,
            }
        )
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]


async def chat_completion_stream(messages: list, model: str = None,
                                 language: str = None) -> AsyncGenerator[str, None]:
    model = model or DEFAULT_MODEL

    system_msg = SYSTEM_PROMPT
    if language:
        lang_names = {
            "ur": "Urdu", "hi": "Hindi", "en": "English", "ar": "Arabic",
            "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese",
            "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "tr": "Turkish",
            "bn": "Bengali", "ru": "Russian", "it": "Italian", "nl": "Dutch",
            "pl": "Polish", "th": "Thai", "vi": "Vietnamese", "id": "Indonesian",
        }
        lang_name = lang_names.get(language, language)
        system_msg += f" The user is speaking {lang_name}. Respond in {lang_name}."

    full_messages = [{"role": "system", "content": system_msg}] + messages

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": full_messages,
                "stream": True,
            }
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "message" in data:
                            yield data["message"].get("content", "")
                    except json.JSONDecodeError:
                        continue


async def check_ollama() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False
