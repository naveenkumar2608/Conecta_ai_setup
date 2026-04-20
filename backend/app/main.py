# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import v1_router
from app.api.middleware.auth_middleware import AzureADAuthMiddleware
from app.api.middleware.error_handler import global_exception_handler
from app.api.middleware.rate_limiter import RateLimiterMiddleware
from app.config import get_settings
from app.dependencies import init_services, shutdown_services
from app.utils.logging_config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    setup_logging()
    await init_services()
    yield
    await shutdown_services()


app = FastAPI(
    title="CONNECTA AI Coaching Platform",
    version="1.0.0",
    docs_url="/api/docs",
    lifespan=lifespan,
)

# Middleware (order matters — outermost first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(AzureADAuthMiddleware)
app.add_exception_handler(Exception, global_exception_handler)

# Routes
app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "connecta-coaching-api"}
