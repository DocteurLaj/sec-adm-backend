from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class ClientRegisterRequest(BaseModel):
    email: str
    phone: str | None = None
    fullName: str
    password: str
    address: str | None = None
    meterNumber: str | None = None
    contractType: str | None = None


class TokenResponse(BaseModel):
    accessToken: str
    refreshToken: str
    tokenType: str = "bearer"
    role: str
    userId: int
    email: str


class RefreshRequest(BaseModel):
    refreshToken: str


class ForgotPasswordRequest(BaseModel):
    email: str
    actorType: str = "client"


class ResetPasswordRequest(BaseModel):
    token: str
    newPassword: str


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str


class ChangeEmailRequest(BaseModel):
    currentPassword: str
    newEmail: str


class VerifyEmailRequest(BaseModel):
    token: str | None = None
    email: str | None = None
    code: str | None = None
    actorType: str = "client"


class ResendVerificationRequest(BaseModel):
    email: str
    actorType: str = "client"


class LogoutRequest(BaseModel):
    refreshToken: str | None = None
