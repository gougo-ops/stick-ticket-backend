from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin_user
from app.models.product import Product
from app.models.ticket_request import TicketRequest
from app.models.user import User
from app.schemas.product import ProductResponse
from app.schemas.ticket_request import TicketRequestResponse
from app.schemas.user import UserResponse

router = APIRouter()


@router.get(
    "/users",
    response_model=List[UserResponse],
    summary="所有用户列表",
)
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """返回所有用户列表，按ID升序排列。"""
    users = db.execute(
        select(User).order_by(User.id.asc())
    ).scalars().all()
    return users

# ─── Request Schemas ──────────────────────────────────────────

class ApproveRejectBody(BaseModel):
    admin_note: Optional[str] = Field(None, examples=["继续加油"])

class AdjustBalanceBody(BaseModel):
    delta: int = Field(..., examples=[50])

class ProductCreateBody(BaseModel):
    name: str = Field(..., examples=["新商品"])
    image_url: Optional[str] = Field(None, examples=["🎁"])
    price: int = Field(..., gt=0, examples=[10])
    stock: int = Field(-1, examples=[-1])

class ProductUpdateBody(BaseModel):
    name: Optional[str] = Field(None)
    image_url: Optional[str] = Field(None)
    price: Optional[int] = Field(None, gt=0)
    stock: Optional[int] = Field(None)
    is_available: Optional[bool] = Field(None)

# ─── Endpoints ─────────────────────────────────────────────────

@router.get(
    "/requests/pending",
    response_model=List[TicketRequestResponse],
    summary="待审批申请列表",
)
def list_pending_requests(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """返回所有 status='pending' 的增券申请。"""
    requests = db.execute(
        select(TicketRequest)
        .where(TicketRequest.status == "pending")
        .order_by(TicketRequest.created_at.asc())
    ).scalars().all()
    return requests


@router.post(
    "/requests/{request_id}/approve",
    response_model=TicketRequestResponse,
    summary="通过增券申请",
)
def approve_request(
    request_id: int,
    body: ApproveRejectBody,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """通过申请：状态改为 approved，增加用户棒棒券余额。"""
    req = db.execute(
        select(TicketRequest).where(TicketRequest.id == request_id)
    ).scalar_one_or_none()

    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="申请不存在")
    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该申请已处理")

    # 锁定用户行
    user = db.execute(
        select(User).where(User.id == req.user_id).with_for_update()
    ).scalar_one()

    # 更新申请
    req.status = "approved"
    req.admin_id = admin.id
    req.admin_note = body.admin_note

    # 增加用户券数
    user.ticket_balance += req.amount

    db.commit()
    db.refresh(req)
    return req


@router.post(
    "/requests/{request_id}/reject",
    response_model=TicketRequestResponse,
    summary="拒绝增券申请",
)
def reject_request(
    request_id: int,
    body: ApproveRejectBody,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """拒绝申请：状态改为 rejected，不修改用户余额。"""
    req = db.execute(
        select(TicketRequest).where(TicketRequest.id == request_id)
    ).scalar_one_or_none()

    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="申请不存在")
    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该申请已处理")

    req.status = "rejected"
    req.admin_id = admin.id
    req.admin_note = body.admin_note

    db.commit()
    db.refresh(req)
    return req


@router.post(
    "/users/{user_id}/adjust-balance",
    summary="手动调整用户券数",
)
def adjust_balance(
    user_id: int,
    body: AdjustBalanceBody,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """调整指定用户的棒棒券余额。delta 为正增加，为负减少。"""
    user = db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    user.ticket_balance += body.delta
    db.commit()

    return {
        "message": "调整成功",
        "user_id": user.id,
        "new_balance": user.ticket_balance,
    }


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="添加商品",
)
def create_product(
    body: ProductCreateBody,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """管理员添加新商品。"""
    product = Product(
        name=body.name,
        image_url=body.image_url,
        price=body.price,
        stock=body.stock,
        is_available=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put(
    "/products/{product_id}",
    response_model=ProductResponse,
    summary="修改商品",
)
def update_product(
    product_id: int,
    body: ProductUpdateBody,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """管理员修改商品信息。只更新传入的字段。"""
    product = db.execute(
        select(Product).where(Product.id == product_id)
    ).scalar_one_or_none()

    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product
