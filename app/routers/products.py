from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.product import Product
from app.schemas.product import ProductResponse

router = APIRouter()


@router.get(
    "/products",
    response_model=List[ProductResponse],
    summary="获取可用商品列表",
)
def list_products(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """返回所有上架的商品（is_available = true）。"""
    products = db.execute(
        select(Product).where(Product.is_available == True)
    ).scalars().all()
    return [ProductResponse.model_validate(p) for p in products]
