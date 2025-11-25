from pydantic import BaseModel


class FirebaseUser(BaseModel):
    user_id: str
    email: str | None = None
    name: str | None = None
    picture: str | None = None


class AuthProfileResponse(BaseModel):
    userId: str
    email: str | None = None
    displayName: str | None = None
    photoUrl: str | None = None



