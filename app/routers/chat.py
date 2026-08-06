from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.dependencies import get_current_user

router = APIRouter()


@router.post("/chat", summary="AI 对话（待实现）")
def chat(current_user=Depends(get_current_user)):
    """占位端点。AI 对话功能将在后续版本实现。"""
    return JSONResponse(
        status_code=501,
        content={"message": "AI 聊天功能尚未开放，敬请期待"},
    )
