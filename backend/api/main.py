"""FastAPI application."""
from __future__ import annotations
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import ALLOWED_ORIGINS, llm_mode
from .db import init_db
from .routes import conversations, strategies, catalog, llm_diag

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

app = FastAPI(title="QuantFlow API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations.router)
app.include_router(strategies.router)
app.include_router(catalog.router)
app.include_router(llm_diag.router)


@app.on_event("startup")
def on_startup():
    init_db()
    logging.info("QuantFlow API ready · llm_mode=%s", llm_mode())


@app.get("/health")
def health():
    return {"status": "ok", "llm_mode": llm_mode()}


@app.get("/")
def root():
    return {
        "name": "QuantFlow API",
        "version": "0.1.0",
        "endpoints": [
            "/health",
            "/conversations",
            "/conversations/{id}",
            "/conversations/{id}/messages",
            "/strategies",
            "/strategies/{id}",
            "/catalog/indicators",
            "/catalog/templates",
            "/catalog/instruments",
        ],
    }
