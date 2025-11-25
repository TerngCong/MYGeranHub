from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ChatSessionResponse(BaseModel):
    sessionId: str
    userId: str


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatMessageRequest(BaseModel):
    prompt: str
    sessionId: Optional[str] = None


class ChatMessageResponse(BaseModel):
    sessionId: str
    reply: str
    messages: List[ChatMessage]



