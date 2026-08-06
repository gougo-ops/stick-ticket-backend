from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Default: local SQLite (always works for development)
    # Production: set DATABASE_URL env var (Render/Railway dashboard or .env)
    DATABASE_URL: str = "sqlite:///./stick_ticket.db"
    JWT_SECRET: str = "change-me-in-production"
    JWT_EXPIRE_HOURS: int = 24

    class Config:
        env_file = ".env"


settings = Settings()
