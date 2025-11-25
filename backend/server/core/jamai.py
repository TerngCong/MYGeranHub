from __future__ import annotations

from typing import Iterable, List, Sequence


class JamAIClient:
    """Placeholder JamAI client.

    Once the JamAI Base endpoints are available we can replace this stub with
    real HTTP calls. For now it simply echoes the latest prompt to keep the API
    contract stable for the frontend.
    """

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url

    def generate_reply(self, prompt: str, context: Sequence[str] | None = None) -> str:
        context_preview = ""
        if context:
            last_items: List[str] = list(context)[-2:]
            context_preview = " | ".join(last_items)

        if context_preview:
            return f"(JamAI placeholder) Based on {context_preview}, here's my take: {prompt}"

        return f"(JamAI placeholder) I received your message: {prompt}"



