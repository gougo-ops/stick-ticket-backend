"""
初始化种子数据脚本。
运行方式: python init_data.py
创建管理员账户和 5 个初始商品（与 Flutter MockData 一致）。
"""

from app.database import SessionLocal, init_db
from app.models.user import User
from app.models.product import Product
from app.utils.security import hash_password


def seed():
    # 确保表已创建
    init_db()

    db = SessionLocal()

    try:
        # ── 创建管理员账户 ──
        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            role="admin",
            ticket_balance=99999,
        )
        db.add(admin)

        # ── 创建 5 个初始商品 ──
        products = [
            Product(name="咖啡", image_url="☕", price=5),
            Product(name="蛋糕", image_url="🍰", price=15),
            Product(name="盲盒", image_url="🎁", price=30),
            Product(name="电影票", image_url="🎬", price=50),
            Product(name="图书", image_url="📚", price=20),
        ]
        for p in products:
            db.add(p)

        db.commit()
        print("[OK] Seed data initialized!")
        print("  Admin: admin / admin123")
        print("  Products: coffee(5) cake(15) mystery-box(30) movie-ticket(50) book(20)")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Seed failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
