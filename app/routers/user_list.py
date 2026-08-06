from sqlalchemy import select

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin_user
from app.models.user import User

router = APIRouter()


@router.get("/users", summary="所有用户列表")
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    users = db.execute(
        select(User).order_by(User.id.asc())
    ).scalars().all()
    return [
        {"id": u.id, "username": u.username, "role": u.role, "ticket_balance": u.ticket_balance}
        for u in users
    ]
