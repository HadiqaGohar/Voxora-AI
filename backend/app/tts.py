import edge_tts
import asyncio
import json
from typing import Optional


async def list_voices():
    voices = await edge_tts.list_voices()
    return voices


def get_voices_sync():
    return asyncio.run(list_voices())


async def synthesize(text: str, voice: str = "en-US-AriaNeural",
                     rate: str = "+0%", pitch: str = "+0Hz"):
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data


async def synthesize_stream(text: str, voice: str = "en-US-AriaNeural",
                            rate: str = "+0%", pitch: str = "+0Hz"):
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            yield chunk["data"]


async def get_voices_by_language(language: str):
    voices = await list_voices()
    return [v for v in voices if v["Locale"].startswith(language)]


async def detect_language(text: str) -> str:
    lang_chars = {
        "ur": range(0x0600, 0x06FF + 1),
        "ar": range(0x0600, 0x06FF + 1),
        "hi": range(0x0900, 0x097F + 1),
        "zh": range(0x4E00, 0x9FFF + 1),
        "ja": range(0x3040, 0x309F + 1),
        "ko": range(0xAC00, 0xD7AF + 1),
        "th": range(0x0E00, 0x0E7F + 1),
    }

    for lang, char_range in lang_chars.items():
        for char in text:
            if ord(char) in char_range:
                return lang

    return "en"


async def auto_voice_for_text(text: str) -> str:
    lang = await detect_language(text)
    voice_map = {
        "ur": "ur-PK-UzmaNeural",
        "ar": "ar-SA-ZariyahNeural",
        "hi": "hi-IN-SwaraNeural",
        "zh": "zh-CN-XiaoxiaoNeural",
        "ja": "ja-JP-NanamiNeural",
        "ko": "ko-KR-SunHiNeural",
        "th": "th-TH-PremwadeeNeural",
        "en": "en-US-AriaNeural",
    }
    return voice_map.get(lang, "en-US-AriaNeural")
