from contextlib import asynccontextmanager
from sqlalchemy import select, func

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import init_db, SessionLocal
from app.models.user import User
from app.models.product import Product
from app.utils.security import hash_password
from app.routers import (
    auth,
    user,
    products,
    orders,
    ticket_requests,
    admin,
    chat,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables and seed initial data if empty."""
    init_db()

    # Auto-seed: create admin + sample products if DB is empty
    db = SessionLocal()
    try:
        product_count = db.execute(select(func.count()).select_from(Product)).scalar()
        if product_count == 0:
            # Create admin user
            admin_user = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
                ticket_balance=99999,
            )
            db.add(admin_user)

            # Create sample products
            sample_products = [
                Product(name="咖啡", image_url="☕", price=5),
                Product(name="蛋糕", image_url="🍰", price=15),
                Product(name="盲盒", image_url="🎁", price=30),
                Product(name="电影票", image_url="🎬", price=50),
                Product(name="图书", image_url="📚", price=20),
            ]
            for p in sample_products:
                db.add(p)

            db.commit()
            print("[OK] Auto-seeded admin + 5 products")
    except Exception as e:
        db.rollback()
        print(f"[WARN] Seed skipped: {e}")
    finally:
        db.close()

    yield


app = FastAPI(
    title="Stick Ticket API",
    description="棒棒券 App 后端服务",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Flutter web apps as static files
_web_dir = Path(__file__).resolve().parent.parent / "web"
if _web_dir.exists():
    app.mount("/app", StaticFiles(directory=str(_web_dir / "user"), html=True), name="user_app")
    app.mount("/admin", StaticFiles(directory=str(_web_dir / "admin"), html=True), name="admin_app")

# Register routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(user.router, prefix="/api/user", tags=["User"])
app.include_router(products.router, tags=["Products"])
app.include_router(orders.router, tags=["Orders"])
app.include_router(ticket_requests.router, tags=["Ticket Requests"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(chat.router, tags=["Chat"])

# Debug: print registered routes
for route in app.routes:
    if hasattr(route, 'path'):
        print(f"  [route] {route.path}")
