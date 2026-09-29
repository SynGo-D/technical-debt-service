from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # Required
    llm_api_key: str

    # Automatically configured
    llm_base_url: str = "https://api.openai.com/v1"

    llm_model: str = "gpt-5.6-luna"

    developer_hourly_rate: float = 25.0

    database_url: str

    port: int = 5003

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()