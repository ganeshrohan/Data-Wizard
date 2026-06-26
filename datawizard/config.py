# config.py – environment configuration
"""Configuration handling using pydantic BaseSettings.
Loads settings from a .env file (if present) and provides type‑safe defaults.
"""

from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    SNOWFLAKE_ACCOUNT: str = Field(..., env="SNOWFLAKE_ACCOUNT")
    SNOWFLAKE_USER: str = Field(..., env="SNOWFLAKE_USER")
    SNOWFLAKE_PASSWORD: str = Field(..., env="SNOWFLAKE_PASSWORD")
    # Add other secrets as needed

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Instantiate a singleton for import elsewhere
settings = Settings()
