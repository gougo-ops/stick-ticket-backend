from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:wjy666888@db.kggyeugjwlmntzxmwfru.supabase.co:5432/postgres?sslmode=require"
    JWT_SECRET: str = "change-me-in-production"
    JWT_EXPIRE_HOURS: int = 24

    class Config:
        env_file = ".env"


settings = Settings()
