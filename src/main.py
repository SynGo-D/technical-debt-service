import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agents.classification_agent import ClassificationAgent
from .agents.estimation_agent import EstimationAgent
from .agents.llm_client import LLMClient
from .api.debt import router as debt_router
from .api.health import router as health_router
from .config import settings
from .infrastructure.analysis_repository import AnalysisEngineRepository
from .infrastructure.database import (
    AnalysisSessionLocal,
    AsyncSessionLocal,
    analysis_engine,
    engine,
)
from .infrastructure.debt_repository import DebtRepository
from .infrastructure.models import create_tables
from .messaging.consumer import AnalysisCompletedConsumer
from .services.aggregator import DebtAggregator
from .services.cost_calculator import CostCalculator
from .services.debt_service import DebtService
from .services.health_calculator import HealthCalculator


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def build_debt_service(llm: LLMClient) -> DebtService:

    return DebtService(
        classification_agent=ClassificationAgent(llm),
        estimation_agent=EstimationAgent(llm),
        aggregator=DebtAggregator(),
        cost_calculator=CostCalculator(settings.developer_hourly_rate),
        health_calculator=HealthCalculator(),
        concurrency=settings.llm_concurrency,
        max_findings=settings.max_findings_per_run,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.debt_repository = DebtRepository(AsyncSessionLocal)

    app.state.analysis_repository = AnalysisEngineRepository(AnalysisSessionLocal)

    # Fail fast, with a message that says WHICH database is the problem.
    for name, repo in (
        ("technical-debt DB (DATABASE_URL)", app.state.debt_repository),
        ("analysis-engine DB (ANALYSIS_DATABASE_URL)", app.state.analysis_repository),
    ):
        try:
            await repo.ping()
            logger.info("Connected to %s", name)
        except Exception:
            logger.error("Cannot connect to %s", name)
            raise

    await create_tables(engine)

    if not settings.llm_api_key:
        logger.warning(
            "LLM_API_KEY is empty: agents will fall back to rule-based estimates"
        )

    llm = LLMClient()

    app.state.debt_service = build_debt_service(llm)

    # Consuming analysis.completed is optional: without a broker URL the
    # service still works exactly as before, driven by the HTTP endpoint.
    # A broker that cannot be reached is logged and skipped rather than
    # fatal, because the button is a complete fallback for it.
    app.state.rabbitmq_connection = None
    if settings.rabbitmq_url:
        try:
            import aio_pika

            app.state.rabbitmq_connection = await aio_pika.connect_robust(
                settings.rabbitmq_url
            )
            channel = await app.state.rabbitmq_connection.channel()
            await AnalysisCompletedConsumer(
                debt_service=app.state.debt_service,
                debt_repository=app.state.debt_repository,
                analysis_repository=app.state.analysis_repository,
            ).start(channel)
        except Exception:
            logger.exception(
                "Could not start the analysis.completed consumer. Debt can "
                "still be calculated through the API."
            )
            app.state.rabbitmq_connection = None
    else:
        logger.info("RABBITMQ_URL is empty: debt is calculated on request only")

    yield

    if app.state.rabbitmq_connection is not None:
        await app.state.rabbitmq_connection.close()
    await llm.aclose()
    await engine.dispose()
    await analysis_engine.dispose()


app = FastAPI(
    title="Technical Debt Service",
    description="Multi-agent technical debt calculation service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
async def root():

    return {
        "service": "Technical Debt Service",
        "status": "running",
    }


app.include_router(health_router)
app.include_router(debt_router)
