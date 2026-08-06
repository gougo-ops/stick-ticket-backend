from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, examples=["user1"])
    password: str = Field(..., min_length=1, max_length=100, examples=["user1"])


class UserLoginRequest(BaseModel):
    username: str = Field(..., examples=["user1"])
    password: str = Field(..., examples=["user1"])


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    ticket_balance: int

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
