from dotenv import load_dotenv
from pydantic import SecretStr
from pydantic_settings import BaseSettings

load_dotenv(".env")


class Settings(BaseSettings):
    foundry_endpoint: str | None = None
    foundry_model: str | None = None
    foundry_api_key: SecretStr | None = None

    bedrock_endpoint: str | None = None
    bedrock_model: str | None = None
    bedrock_api_key: SecretStr | None = None

    opencode_endpoint: str | None = None
    opencode_model: str | None = None
    opencode_api_key: SecretStr | None = None

    openrouter_endpoint: str | None = None
    openrouter_model: str | None = None
    openrouter_api_key: SecretStr | None = None


settings = Settings()
