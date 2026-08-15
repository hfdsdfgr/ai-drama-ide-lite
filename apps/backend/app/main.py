"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    assets,
    asset_versions,
    generation,
    health,
    images,
    jobs,
    novels,
    production_graph,
    projects,
    providers,
    script,
    story,
)
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.db.database import init_db
from app.services.adapters.manager import ProviderManager
from app.services.ai_novel import AiNovelService
from app.services.ai_script import AiScriptService
from app.services.asset_service import AssetGenerationService
from app.services.asset_version_service import AssetVersionService
from app.services.generation_service import GenerationService
from app.services.image_generation_service import ImageGenerationService
from app.services.image_result_service import ImageResultService
from app.services.job_store import JobStore
from app.services.job_worker import JobWorker
from app.services.project_repo import migrate_legacy_json_projects
from app.services.production_graph import ProductionGraphService
from app.services.provider_repo import ProviderRepository
from app.services.secret_store import KeyringSecretStore, SecretStore
from app.services.story_analysis import StoryAnalysisService

logger = get_logger("main")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.job_worker.start()
    try:
        yield
    finally:
        app.state.job_worker.stop()


def create_app(
    settings: Settings | None = None,
    secret_store: SecretStore | None = None,
) -> FastAPI:
    config = settings or get_settings()
    setup_logging(level=config.log_level, log_dir=config.data_dir / "logs")
    init_db(config.db_path)
    migrate_legacy_json_projects(config.db_path, config.projects_dir)

    app = FastAPI(title=config.app_name, version="0.1.1", lifespan=_lifespan)
    app.state.settings = config
    app.state.secret_store = secret_store or KeyringSecretStore()
    app.state.provider_manager = ProviderManager(
        ProviderRepository(config.db_path, app.state.secret_store)
    )
    app.state.job_store = JobStore(config.db_path)
    app.state.image_result_service = ImageResultService(
        config.db_path, config.projects_dir
    )
    app.state.job_worker = JobWorker(
        app.state.job_store,
        app.state.provider_manager,
        config.data_dir / "generation_tests",
        image_result_service=app.state.image_result_service,
    )
    app.state.generation_service = GenerationService(
        app.state.job_store,
        app.state.provider_manager,
        config.data_dir / "generation_tests",
    )
    app.state.asset_version_service = AssetVersionService(
        config.db_path, config.projects_dir
    )
    app.state.image_generation_service = ImageGenerationService(
        app.state.generation_service,
        app.state.provider_manager,
        config.db_path,
        app.state.asset_version_service,
    )
    app.state.story_service = StoryAnalysisService(
        app.state.provider_manager, config.db_path
    )
    app.state.asset_service = AssetGenerationService(
        app.state.job_store, app.state.provider_manager, config.db_path
    )
    app.state.production_graph_service = ProductionGraphService(config.db_path)
    app.state.ai_novel_service = AiNovelService(
        app.state.provider_manager, config.db_path
    )
    app.state.ai_script_service = AiScriptService(
        app.state.provider_manager, config.db_path
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(novels.router)
    app.include_router(providers.router)
    app.include_router(providers.models_router)
    app.include_router(generation.router)
    app.include_router(images.router)
    app.include_router(jobs.router)
    app.include_router(story.router)
    app.include_router(script.router)
    app.include_router(assets.router)
    app.include_router(asset_versions.router)
    app.include_router(production_graph.router)
    logger.info("Application started (env=%s)", config.env)
    return app


app = create_app()
