from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tags import tags_metadata
from app.api.crawler.routes import crawler_api


def create_app() -> FastAPI:
    app = FastAPI(
        title="Crawler for Discovering Product URLs on E-commerce Websites", openapi_tags=tags_metadata, version="1.0.0"
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(crawler_api, prefix='/api/crawler', tags=["crawler"])

    return app
