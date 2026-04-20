# backend/app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1.chat import router as chat_router
from app.api.v1.upload import router as upload_router
from app.api.v1.history import router as history_router
from app.api.v1.auth import router as auth_router

v1_router = APIRouter()

v1_router.include_router(chat_router, prefix="/chat", tags=["Chat"])
v1_router.include_router(upload_router, prefix="/upload", tags=["Upload"])
v1_router.include_router(history_router, prefix="/history", tags=["History"])
v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
