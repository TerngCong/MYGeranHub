from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import auth, chat
from .core import settings

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}