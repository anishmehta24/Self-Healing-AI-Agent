from __future__ import annotations

from fastapi import FastAPI

from Backend.app.api import build_router
from Backend.app.config import settings
from Backend.app.graph import WorkflowEngine
from Backend.app.llm import LLMClient
from Backend.app.persistence import IncidentStore


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
    app.include_router(build_router(engine))
    return app


app = create_app()
