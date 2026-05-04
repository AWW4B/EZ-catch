from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.models.database import create_all
from src.api.v1.ingest import router as ingest_router
from src.api.v1.user_routes import router as user_router
from src.api.v1.admin_routes import router as admin_router

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Agent Monitor — Backend API",
    description=(
        "Receives intercepted agent events from the local buffer forwarder "
        "and exposes them to the admin dashboard."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow the Next.js admin panel (and any localhost origin in dev)
# ---------------------------------------------------------------------------
_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Startup: ensure tables exist
# ---------------------------------------------------------------------------
@app.on_event("startup")
def on_startup() -> None:
    create_all()


# ---------------------------------------------------------------------------
# Health check — used by Docker healthcheck and the admin panel status pill
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(ingest_router)
app.include_router(user_router)
app.include_router(admin_router)
