from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _to_asyncpg(url: str) -> str:
    """SQLAlchemy's async engine needs an async driver in the URL. A plain
    `postgresql://` makes create_async_engine fail - normalise it instead."""
    for prefix in ("postgresql://", "postgres://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    # This service's own DB (debt_reviews / debt_issues) - read/write.
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/technical_debt_db"
    )

    # analysis-engine's DB (analysis_results / findings) - read-only.
    # Default = analysis-engine's own docker-compose.yml (host port 5434).
    analysis_database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5434/analysis_engine_db"
    )

    # Empty key -> agents fall back to rule-based estimates.
    llm_api_key: str = ""

    llm_base_url: str = "https://api.openai.com/v1"

    llm_model: str = "gpt-5.6-luna"

    llm_timeout_seconds: float = 120.0

    llm_concurrency: int = 5

    developer_hourly_rate: float = 25.0

    # Findings sent through the two agents per run (2 LLM calls each).
    # Highest-severity findings are kept first; the rest are reported as skipped.
    max_findings_per_run: int = 200

    # SonarQube is only contacted by the rule-catalog sync (weekly, in the
    # background) - never while a pull request is being calculated.
    sonar_url: str = "http://localhost:9000"

    sonar_token: str = ""

    sonar_languages: str = "js,ts,py"

    sonar_sync_interval_hours: int = 168  # one week; 0 disables the automatic sync

    frontend_origin: str = "http://localhost:3000"

    port: int = 5003

    @field_validator("database_url", "analysis_database_url")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        return _to_asyncpg(v)


settings = Settings()
