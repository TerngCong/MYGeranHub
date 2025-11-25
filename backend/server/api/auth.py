from fastapi import APIRouter, Depends

from ..core.deps import get_current_user
from ..models.auth import AuthProfileResponse, FirebaseUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/profile", response_model=AuthProfileResponse)
def read_profile(current_user: FirebaseUser = Depends(get_current_user)) -> AuthProfileResponse:
    return AuthProfileResponse(
        userId=current_user.user_id,
        email=current_user.email,
        displayName=current_user.name,
        photoUrl=current_user.picture,
    )



