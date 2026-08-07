import os
import sys

from pydantic_settings import BaseSettings

# ── 生产环境检测 ──────────────────────────────────────────────
IS_RAILWAY = bool(os.getenv("RAILWAY_SERVICE_ID"))
IS_RENDER = bool(os.getenv("RENDER"))
IS_PRODUCTION = IS_RAILWAY or IS_RENDER


class Settings(BaseSettings):
    # 默认使用 SQLite（本地开发开箱即用）
    # 生产环境务必通过 Railway/Render Dashboard 设置 DATABASE_URL 环境变量
    # 指向 PostgreSQL（Railway 插件 / Supabase / 外部数据库）
    DATABASE_URL: str = "sqlite:///./stick_ticket.db"
    JWT_SECRET: str = "change-me-in-production"
    JWT_EXPIRE_HOURS: int = 24

    class Config:
        env_file = ".env"


settings = Settings()

# ── 生产环境 SQLite 警告 ──────────────────────────────────────
if IS_PRODUCTION and settings.DATABASE_URL.startswith("sqlite"):
    print(
        "\n"
        "=" * 60 + "\n"
        "⚠️  严重警告：生产环境正在使用 SQLite！\n"
        "   每次 Railway/Render 重新部署都会创建全新容器，\n"
        "   SQLite 数据库文件将随之销毁，所有用户数据丢失！\n"
        "   这解释了为什么用户每次都需要重新注册。\n\n"
        "   解决方法：\n"
        "   1. Railway: 在 Dashboard → 项目 → + New → Database → PostgreSQL\n"
        "      插件会自动注入 DATABASE_URL 环境变量，覆盖 SQLite 默认值\n"
        "   2. 或手动设置 DATABASE_URL 指向你的 PostgreSQL 数据库\n"
        "      (Supabase / Railway PG / 外部 PG 均可)\n"
        "=" * 60 + "\n",
        file=sys.stderr,
    )
