from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..services.chat_table_service import chat_table_service
from ..services.grant_manager import grant_agent
from ..core.deps import get_current_user
from ..models.auth import FirebaseUser

router = APIRouter(prefix="/jamai", tags=["jamai"])

@router.post("/session")
def create_chat_session(current_user: FirebaseUser = Depends(get_current_user)):
    try:
        result = chat_table_service.create_chat_table(current_user.user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Simple in-memory session management
sessions = {}

@router.post("/reset")
def reset_chat_session(current_user: FirebaseUser = Depends(get_current_user)):
    """
    Explicitly resets the chat session for the user.
    Call this on Logout or when the user wants to start over.
    """
    user_id = current_user.user_id
    if user_id in sessions:
        del sessions[user_id]
        
    return {"status": "success", "message": "Session reset successfully."}

class ChatRequest(BaseModel):
    message: str

@router.post("/message")
def send_chat_message(request: ChatRequest, current_user: FirebaseUser = Depends(get_current_user)):
    user_id = current_user.user_id
    
    # Get or create session
    if user_id not in sessions:
        sessions[user_id] = {"buffer": "", "status": "IDLE", "user_id": user_id}
    
    session = sessions[user_id]
    
    try:
        # LAZY ROUTER LOGIC
        
        # Case 1: Already in Active Search Mode
        if session["status"] == "ACTIVE_SEARCH":
            result = grant_agent.process_input(session, request.message)
            
            # Check if done
            if result.get("status") == "DONE":
                session["status"] = "IDLE" # Reset to IDLE after verdict
                session["buffer"] = ""
                
            return {
                "status": "reply", # Frontend expects "reply" to show message
                "message": [result.get("reply", "")]
            }

        # Case 2: IDLE Mode (Normal Chat)
        else:
            # Call the Chat Table (General Agent)
            # We use send_message directly to check for the token ourselves
            chat_response = chat_table_service.send_message(user_id, request.message)
            
            if "<<REDIRECT_TO_SEARCH>>" in chat_response:
                # Switch to Active Search
                session["status"] = "ACTIVE_SEARCH"
                
                # Immediately process the input that triggered the redirect
                result = grant_agent.process_input(session, request.message)
                
                # Check if done (unlikely on first turn, but possible)
                if result.get("status") == "DONE":
                    session["status"] = "IDLE"
                    session["buffer"] = ""
                
                return {
                    "status": "reply",
                    "message": [result.get("reply", "")]
                }
            else:
                # Normal conversation
                return {
                    "status": "reply",
                    "message": [chat_response]
                }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))