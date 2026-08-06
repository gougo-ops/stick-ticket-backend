from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.ticket_request import TicketRequest
from app.models.user import User
from app.schemas.ticket_request import TicketRequestCreate, TicketRequestResponse

router = APIRouter()


@router.post(
    "/ticket-requests",
    response_model=TicketRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="提交增券申请",
)
def create_request(
    body: TicketRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交增券申请。amount 必须大于 0。申请状态初始为 pending。"""
    if body.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="申请数量必须大于0",
        )

    req = TicketRequest(
        user_id=current_user.id,
        amount=body.amount,
        reason=body.reason,
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get(
    "/ticket-requests/history",
    response_model=List[TicketRequestResponse],
    summary="增券申请历史",
)
def list_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回当前用户的增券申请历史，按时间倒序。"""
    requests = db.execute(
        select(TicketRequest)
        .where(TicketRequest.user_id == current_user.id)
        .order_by(TicketRequest.created_at.desc())
    ).scalars().all()
    return requests
