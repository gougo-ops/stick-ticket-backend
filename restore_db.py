"""
数据库恢复脚本
将 JSON 备份数据导入到目标数据库
用法:
  python restore_db.py backup_data.json  <DATABASE_URL>
  python restore_db.py backup_data.json   # 使用 .env 中的 DATABASE_URL
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


TABLES = ["ticket_requests", "orders", "products", "users"]


def restore(backup_file: str, database_url: str):
    # 连接目标数据库
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    engine = create_engine(
        database_url,
        connect_args=connect_args,
        # echo=True,   # 调试时取消注释
    )

    # 1. 确保表存在（复用 ORM 的 create_all）
    from app.database import Base
    Base.metadata.create_all(bind=engine)

    Session = sessionmaker(bind=engine)
    db = Session()

    # 2. 读取备份
    with open(backup_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"📦 备份文件: {backup_file}")
    print(f"   导出时间: {data.get('exported_at', 'unknown')}")
    print(f"   数据统计: {data.get('counts', {})}")
    print()

    try:
        is_postgres = "postgresql" in database_url

        # 3. 清空现有数据（按外键依赖顺序）
        print("🗑️  清空旧数据...")
        for table in TABLES:
            db.execute(text(f"DELETE FROM {table}"))
        db.flush()

        # 4. 导入数据（按依赖顺序: users -> products -> orders, ticket_requests）
        tables_order = ["users", "products", "orders", "ticket_requests"]
        for table_name in tables_order:
            rows = data.get(table_name, [])
            if not rows:
                print(f"   ⏭️  {table_name}: 0 条，跳过")
                continue

            for row in rows:
                columns = ", ".join(row.keys())
                placeholders = ", ".join(f":{k}" for k in row.keys())
                sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                db.execute(text(sql), row)

            print(f"   ✅ {table_name}: {len(rows)} 条")

        db.flush()

        # 5. 重置 PostgreSQL 序列（自增ID 从最大ID+1开始）
        if is_postgres:
            print("\n🔄 重置自增序列...")
            # users
            max_id = db.execute(text("SELECT COALESCE(MAX(id), 0) FROM users")).scalar()
            db.execute(
                text("SELECT setval(pg_get_serial_sequence('users', 'id'), :max_id)"),
                {"max_id": max_id},
            )
            # products
            max_id = db.execute(text("SELECT COALESCE(MAX(id), 0) FROM products")).scalar()
            db.execute(
                text("SELECT setval(pg_get_serial_sequence('products', 'id'), :max_id)"),
                {"max_id": max_id},
            )
            # orders
            max_id = db.execute(text("SELECT COALESCE(MAX(id), 0) FROM orders")).scalar()
            db.execute(
                text("SELECT setval(pg_get_serial_sequence('orders', 'id'), :max_id)"),
                {"max_id": max_id},
            )
            # ticket_requests
            max_id = db.execute(text("SELECT COALESCE(MAX(id), 0) FROM ticket_requests")).scalar()
            db.execute(
                text("SELECT setval(pg_get_serial_sequence('ticket_requests', 'id'), :max_id)"),
                {"max_id": max_id},
            )
            print("   序列已重置 ✅")

        db.commit()
        print(f"\n✅ 恢复完成！")

        # 6. 验证
        print("\n📊 验证：")
        for table_name in tables_order:
            count = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            print(f"   {table_name}: {count} 条")

    except Exception as e:
        db.rollback()
        print(f"\n❌ 恢复失败: {e}")
        raise
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python restore_db.py <backup_file.json> [DATABASE_URL]")
        print("示例: python restore_db.py backup_data.json")
        print("      python restore_db.py backup_data.json postgresql://user:pass@host:5432/db")
        sys.exit(1)

    backup_file = sys.argv[1]

    if len(sys.argv) >= 3:
        db_url = sys.argv[2]
    else:
        from app.config import settings
        db_url = settings.DATABASE_URL

    restore(backup_file, db_url)
