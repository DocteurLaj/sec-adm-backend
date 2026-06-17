from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.bootstrap import run_light_migrations, seed_first_admin
from app.db.session import Base, SessionLocal, engine
from app.models import (
    Admin,
    AuthAuditLog,
    Client,
    EmailVerificationToken,
    Home,
    Meter,
    PasswordResetToken,
    RefreshSession,
    Transaction,
)
from app.routers import admins, auth, clients, homes, meters, transactions


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = (
        Admin,
        AuthAuditLog,
        Client,
        EmailVerificationToken,
        Home,
        Meter,
        PasswordResetToken,
        RefreshSession,
        Transaction,
    )
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        run_light_migrations(db)
        seed_first_admin(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="SEC Admin Backend",
    version="0.1.0",
    description="Administration, authentification, clients, maisons, compteurs et paiements.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admins.router)
app.include_router(clients.router)
app.include_router(homes.router)
app.include_router(meters.router)
app.include_router(transactions.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "database": "mysql"}
