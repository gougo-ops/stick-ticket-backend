"""
数据库备份脚本
导出当前数据库所有数据到 JSON 文件
用法: python backup_db.py [输出文件名]
"""
import json
import sys
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path

# 添加 app 到路径
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.product import Product
from app.models.order import Order
from app.models.ticket_request import TicketRequest


class DateTimeEncoder(json.JSONEncoder):
    """处理 datetime / Decimal 等类型的 JSON 编码"""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def table_to_dict(rows: list) -> list[dict]:
    """将 SQLAlchemy 模型列表转为 dict 列表"""
    result = []
    for row in rows:
        d = {}
        for col in row.__table__.columns:
            d[col.name] = getattr(row, col.name)
        result.append(d)
    return result


def backup(output_file: str = "backup_data.json"):
    db = SessionLocal()
    try:
        # 导出所有表
        users = db.query(User).all()
        products = db.query(Product).all()
        orders = db.query(Order).all()
        requests = db.query(TicketRequest).all()

        data = {
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "counts": {
                "users": len(users),
                "products": len(products),
                "orders": len(orders),
                "ticket_requests": len(requests),
            },
            "users": table_to_dict(users),
            "products": table_to_dict(products),
            "orders": table_to_dict(orders),
            "ticket_requests": table_to_dict(requests),
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, cls=DateTimeEncoder)

        print(f"✅ 备份完成: {output_file}")
        print(f"   用户: {len(users)} 条")
        print(f"   商品: {len(products)} 条")
        print(f"   订单: {len(orders)} 条")
        print(f"   券申请: {len(requests)} 条")
    except Exception as e:
        print(f"❌ 备份失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    filename = sys.argv[1] if len(sys.argv) > 1 else "backup_data.json"
    backup(filename)
