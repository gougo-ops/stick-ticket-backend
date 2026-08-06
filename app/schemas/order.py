from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OrderCreateRequest(BaseModel):
    product_id: int = Field(..., examples=[1])


class OrderResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    product_name: str
    price: int
    created_at: datetime

    class Config:
        from_attributes = True
