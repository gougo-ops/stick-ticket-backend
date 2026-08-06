from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="获取当前用户信息",
)
def get_me(current_user: User = Depends(get_current_user)):
    """返回当前登录用户的 id、用户名、角色、棒棒券余额。"""
    return UserResponse.model_validate(current_user)
