from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserLoginRequest,
    UserRegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.utils.security import hash_password, verify_password, create_token

router = APIRouter()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
)
def register(body: UserRegisterRequest, db: Session = Depends(get_db)):
    """注册新用户。用户名必须唯一。注册成功后自动登录，返回JWT。"""
    # Check duplicate username
    existing = db.execute(
        select(User).where(User.username == body.username)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    # Create user
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role="user",
        ticket_balance=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Return token + user
    token = create_token(user.id, user.role)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="用户登录",
)
def login(body: UserLoginRequest, db: Session = Depends(get_db)):
    """用户登录。验证用户名密码，返回JWT。"""
    user = db.execute(
        select(User).where(User.username == body.username)
    ).scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = create_token(user.id, user.role)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )
