from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import build_router
from app.config import settings
from app.graph import WorkflowEngine
from app.llm import LLMClient
from app.persistence import IncidentStore


def create_app() -> FastAPI:
    store = IncidentStore(settings.database_path)
    llm_client = LLMClient(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    engine = WorkflowEngine(llm_client=llm_client, store=store, max_retries=settings.max_retries)

    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(build_router(engine))
    return app


app = create_app()
