from typing import Optional

from pydantic import BaseModel


class ProductResponse(BaseModel):
    id: int
    name: str
    image_url: Optional[str] = None
    price: int
    stock: int
    is_available: bool

    class Config:
        from_attributes = True
