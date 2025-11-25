from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Sequence, Tuple
from uuid import uuid4

from ..core.jamai import JamAIClient
from ..core.config import settings
from ..models.chat import ChatMessage


@dataclass
class ChatSession:
    id: str
    user_id: str
    messages: List[ChatMessage] = field(default_factory=list)


class ChatService:
    def __init__(self, llm_client: JamAIClient) -> None:
        self._client = llm_client
        self._sessions: Dict[str, ChatSession] = {}
        self._lock = Lock()

    def ensure_session(self, user_id: str) -> ChatSession:
        session_id = user_id  # Simple deterministic session keyed by user
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = ChatSession(id=session_id, user_id=user_id)
            return self._sessions[session_id]

    def append_message(self, session: ChatSession, role: str, content: str) -> ChatMessage:
        message = ChatMessage(
            id=str(uuid4()),
            role=role,  # type: ignore[arg-type]
            content=content,
            createdAt=datetime.now(timezone.utc),
        )
        session.messages.append(message)
        return message

    def generate_reply(self, prompt: str, history: Sequence[ChatMessage]) -> str:
        context = [message.content for message in history]
        return self._client.generate_reply(prompt, context)

    def send_message(self, user_id: str, prompt: str, session_id: str | None = None) -> Tuple[str, ChatSession]:
        session = self.ensure_session(user_id)
        if session_id and session_id != session.id:
            raise PermissionError("Session does not belong to this user.")

        self.append_message(session, "user", prompt)
        reply = self.generate_reply(prompt, session.messages)
        self.append_message(session, "assistant", reply)
        return reply, session


jamai_client = JamAIClient(settings.jamai_base_url)
chat_service = ChatService(jamai_client)



