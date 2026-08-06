from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TicketRequestCreate(BaseModel):
    amount: int = Field(..., gt=0, examples=[20])
    reason: Optional[str] = Field(None, examples=["完成作业奖励"])


class TicketRequestResponse(BaseModel):
    id: int
    user_id: int
    amount: int
    reason: Optional[str] = None
    status: str
    admin_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
