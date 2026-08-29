"""FastAPI application entrypoint."""

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    assets,
    asset_versions,
    dialogue_reviews,
    generation,
    health,
    images,
    jobs,
    novels,
    overview,
    production_graph,
    projects,
    quality,
    providers,
    script,
    story,
    story_reviews,
    version,
    videos,
    visual_reviews,
)
from app.core.config import Settings, get_settings
from app.core.crash_log import install_crash_handler
from app.core.errors import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.db.database import init_db
from app.services.data_migration import migrate_data_dir
from app.services.adapters.manager import ProviderManager
from app.services.ai_novel import AiNovelService
from app.services.ai_script import AiScriptService
from app.services.asset_service import AssetGenerationService
from app.services.audio_dubbing_service import AudioDubbingService
from app.services.asset_version_service import AssetVersionService
from app.services.generation_service import GenerationService
from app.services.image_generation_service import ImageGenerationService
from app.services.image_result_service import ImageResultService
from app.services.job_store import JobStore
from app.services.job_worker import JobWorker
from app.services.lip_sync_service import LipSyncService
from app.services.video_sequence_service import VideoSequenceService
from app.version import APP_VERSION
from app.services.dialogue_review_service import DialogueReviewService
from app.services.visual_review_service import VisualReviewService
from app.services.story_consistency_service import StoryConsistencyService
from app.services.project_repo import migrate_legacy_json_projects
from app.services.production_graph import ProductionGraphService
from app.services.provider_repo import ProviderRepository
from app.services.secret_store import KeyringSecretStore, SecretStore
from app.services.story_analysis import StoryAnalysisService
from app.services.video_generation_service import VideoGenerationService

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
    migrate_data_dir(config.data_dir, frozen=getattr(sys, "frozen", False))
    setup_logging(level=config.log_level, log_dir=config.data_dir / "logs")
    install_crash_handler(config.data_dir / "logs")
    init_db(config.db_path)
    migrate_legacy_json_projects(config.db_path, config.projects_dir)

    app = FastAPI(title=config.app_name, version=APP_VERSION, lifespan=_lifespan)
    app.state.settings = config
    app.state.secret_store = secret_store or KeyringSecretStore()
    app.state.provider_manager = ProviderManager(
        ProviderRepository(config.db_path, app.state.secret_store)
    )
    app.state.job_store = JobStore(config.db_path)
    app.state.asset_version_service = AssetVersionService(
        config.db_path, config.projects_dir
    )
    app.state.image_result_service = ImageResultService(
        config.db_path, config.projects_dir
    )
    app.state.audio_dubbing_service = AudioDubbingService(
        config.db_path,
        app.state.provider_manager,
        app.state.asset_version_service,
        config.projects_dir,
    )
    app.state.lip_sync_service = LipSyncService(
        config.db_path,
        app.state.asset_version_service,
        config.projects_dir,
    )
    app.state.video_sequence_service = VideoSequenceService(
        config.db_path,
        app.state.asset_version_service,
        config.projects_dir,
    )
    app.state.dialogue_review_service = DialogueReviewService(
        config.db_path,
        app.state.provider_manager,
        app.state.asset_version_service,
        config.projects_dir,
    )
    app.state.visual_review_service = VisualReviewService(
        config.db_path,
        app.state.provider_manager,
        app.state.asset_version_service,
        config.projects_dir,
    )
    app.state.story_consistency_service = StoryConsistencyService(
        config.db_path,
        app.state.provider_manager,
    )
    app.state.job_worker = JobWorker(
        app.state.job_store,
        app.state.provider_manager,
        config.data_dir / "generation_tests",
        image_result_service=app.state.image_result_service,
        audio_dubbing_service=app.state.audio_dubbing_service,
        lip_sync_service=app.state.lip_sync_service,
        video_sequence_service=app.state.video_sequence_service,
        dialogue_review_service=app.state.dialogue_review_service,
        visual_review_service=app.state.visual_review_service,
        story_consistency_service=app.state.story_consistency_service,
    )
    app.state.generation_service = GenerationService(
        app.state.job_store,
        app.state.provider_manager,
        config.data_dir / "generation_tests",
    )
    app.state.image_generation_service = ImageGenerationService(
        app.state.generation_service,
        app.state.provider_manager,
        config.db_path,
        app.state.asset_version_service,
    )
    app.state.video_generation_service = VideoGenerationService(
        app.state.generation_service,
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
    app.include_router(overview.router)
    app.include_router(production_graph.router)
    app.include_router(videos.router)
    app.include_router(dialogue_reviews.router)
    app.include_router(visual_reviews.router)
    app.include_router(quality.router)
    app.include_router(story_reviews.router)
    app.include_router(version.router)
    logger.info("Application started (env=%s)", config.env)
    return app


app = create_app()
