from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from server.services.chat_table_service import chat_table_service

router = APIRouter(prefix="/jamai", tags=["jamai"])

class CreateSessionRequest(BaseModel):
    session_id: str

@router.post("/session")
def create_chat_session(request: CreateSessionRequest):
    try:
        result = chat_table_service.create_chat_table(request.session_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
