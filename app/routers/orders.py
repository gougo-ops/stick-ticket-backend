from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.schemas.order import OrderCreateRequest, OrderResponse

router = APIRouter()


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="购买商品",
)
def create_order(
    body: OrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """使用棒棒券购买指定商品。余额不足时返回400错误。"""
    # 1. 查询商品
    product = db.execute(
        select(Product).where(Product.id == body.product_id)
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="商品不存在",
        )
    if not product.is_available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="商品已下架",
        )

    # 2. 加行锁读取用户（防并发）
    user = db.execute(
        select(User).where(User.id == current_user.id).with_for_update()
    ).scalar_one()

    # 3. 检查余额
    if user.ticket_balance < product.price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="棒棒券不足",
        )

    # 4. 检查库存（stock=-1 表示无限）
    if product.stock == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="商品已售罄",
        )
    if product.stock > 0:
        product.stock -= 1

    # 5. 扣券 + 生成订单（在同一事务内）
    user.ticket_balance -= product.price
    order = Order(
        user_id=user.id,
        product_id=product.id,
        price=product.price,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # 6. 返回订单（含商品名，匹配 Flutter Order 模型）
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        product_id=order.product_id,
        product_name=product.name,
        price=order.price,
        created_at=order.created_at,
    )


@router.get(
    "/orders/history",
    response_model=List[OrderResponse],
    summary="订单历史",
)
def list_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回当前用户的订单历史，按时间倒序。"""
    orders = db.execute(
        select(Order)
        .where(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
    ).scalars().all()

    return [
        OrderResponse(
            id=o.id,
            user_id=o.user_id,
            product_id=o.product_id,
            product_name=o.product.name,
            price=o.price,
            created_at=o.created_at,
        )
        for o in orders
    ]
