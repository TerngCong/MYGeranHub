from fastapi import APIRouter, Depends, HTTPException, status

from ..core.deps import get_current_user
from ..models.auth import FirebaseUser
from ..models.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionResponse,
)
from ..services.chat_service import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/session", response_model=ChatSessionResponse)
def create_session(current_user: FirebaseUser = Depends(get_current_user)) -> ChatSessionResponse:
    session = chat_service.ensure_session(current_user.user_id)
    return ChatSessionResponse(sessionId=session.id, userId=session.user_id)


@router.post("/message", response_model=ChatMessageResponse)
def send_message(
    payload: ChatMessageRequest,
    current_user: FirebaseUser = Depends(get_current_user),
) -> ChatMessageResponse:
    try:
        reply, session = chat_service.send_message(
            user_id=current_user.user_id,
            prompt=payload.prompt,
            session_id=payload.sessionId,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return ChatMessageResponse(sessionId=session.id, reply=reply, messages=session.messages)



