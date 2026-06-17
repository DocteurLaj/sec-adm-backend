from datetime import datetime

from pydantic import BaseModel, Field


class ClientCreate(BaseModel):
    email: str
    phone: str | None = None
    fullName: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=128)


class ClientUpdate(BaseModel):
    phone: str | None = None
    fullName: str | None = Field(default=None, min_length=2, max_length=160)
    isActive: bool | None = None


class ClientOut(BaseModel):
    id: int
    email: str
    phone: str | None
    fullName: str
    isActive: bool
    emailVerified: bool
    createdAt: datetime

    model_config = {"from_attributes": True}
