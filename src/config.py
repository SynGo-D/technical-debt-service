from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    database_url: str

    llm_api_key: str

    llm_base_url: str = "https://api.openai.com/v1"

    llm_model: str = "gpt-5.6-mini"

    developer_hourly_rate: float = 25.0

    port: int = 5003

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()