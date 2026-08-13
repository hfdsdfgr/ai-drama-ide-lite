"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import generation, health, novels, projects, providers
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.db.database import init_db
from app.services.adapters.manager import ProviderManager
from app.services.generation_service import GenerationService
from app.services.project_repo import migrate_legacy_json_projects
from app.services.provider_repo import ProviderRepository
from app.services.secret_store import KeyringSecretStore, SecretStore

logger = get_logger("main")


def create_app(
    settings: Settings | None = None,
    secret_store: SecretStore | None = None,
) -> FastAPI:
    config = settings or get_settings()
    setup_logging(level=config.log_level, log_dir=config.data_dir / "logs")
    init_db(config.db_path)
    migrate_legacy_json_projects(config.db_path, config.projects_dir)

    app = FastAPI(title=config.app_name, version="0.1.0")
    app.state.settings = config
    app.state.secret_store = secret_store or KeyringSecretStore()
    app.state.provider_manager = ProviderManager(
        ProviderRepository(config.db_path, app.state.secret_store)
    )
    app.state.generation_service = GenerationService(
        app.state.provider_manager, config.data_dir / "generation_tests"
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
    logger.info("Application started (env=%s)", config.env)
    return app


app = create_app()
