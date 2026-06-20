from datetime import datetime

from pydantic import BaseModel, Field


class PushTokenRegister(BaseModel):
    token: str = Field(min_length=20)
    platform: str = "android"
    deviceId: str | None = None


class PushTokenOut(BaseModel):
    id: int
    token: str
    platform: str
    deviceId: str | None
    isActive: bool
    createdAt: datetime
    updatedAt: datetime
