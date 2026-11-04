"""Text-to-speech behind one interface. Default is NullTTS: large on-screen Korean text."""

from __future__ import annotations

from typing import Protocol


class TTSProvider(Protocol):
    name: str

    async def speak(self, text_ko: str) -> bytes | None: ...


class NullTTS:
    name = "null"

    async def speak(self, text_ko: str) -> bytes | None:
        return None  # the client shows text_ko in large type instead
