import hashlib
import os
import random
import smtplib
import threading
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import bcrypt
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, Column, DateTime, String, create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

app = FastAPI(title="Galaxy Auth Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("JWT_SECRET", "CHANGE_ME_generate_with_openssl_rand_hex_32")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "CHANGE_ME_internal_service_key")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/galaxy")
ACCESS_EXP_MIN = int(os.getenv("ACCESS_EXP_MIN", "60"))
REFRESH_EXP_DAYS = int(os.getenv("REFRESH_EXP_DAYS", "30"))
DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@test.com")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "Test1234!")
DEFAULT_ADMIN_ORG_NAME = os.getenv("DEFAULT_ADMIN_ORG_NAME", "Test Corp")
DEFAULT_EDGE_API_KEY = os.getenv("DEFAULT_EDGE_API_KEY", "edge-planet-local")
DEFAULT_EDGE_ORG_NAME = os.getenv("DEFAULT_EDGE_ORG_NAME", "Edge Demo")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@galaxy.local")
OTP_TTL_MINUTES = int(os.getenv("OTP_TTL_MINUTES", "10"))

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
security = HTTPBearer(auto_error=False)

_rate_lock = threading.Lock()
_rate_windows: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    plan = Column(String, default="free")
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    org_id = Column(String, nullable=False, index=True)
    role = Column(String, default="viewer")
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    otp_code = Column(String, nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    key_hash = Column(String, unique=True, nullable=False, index=True)
    key_fingerprint = Column(String, unique=True, nullable=False, index=True)
    device_id = Column(String, nullable=False)
    org_id = Column(String, nullable=False, index=True)
    name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


class RegisterReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    org_name: str = Field(min_length=1)


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class VerifyOtpReq(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=4, max_length=12)


class ResendOtpReq(BaseModel):
    email: EmailStr


class RegisterResponse(BaseModel):
    message: str
    requires_otp: bool = True
    dev_otp: str | None = None


class CreateApiKeyReq(BaseModel):
    device_id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    org_id: str
    role: str


class ApiKeyResolveRequest(BaseModel):
    api_key: str = Field(min_length=1)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_pw(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def fingerprint_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def make_token(data: dict, *, minutes: int | None = None, days: int | None = None, token_type: str = "access") -> str:
    payload = {**data, "type": token_type}
    if minutes is not None:
        payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    elif days is not None:
        payload["exp"] = datetime.now(timezone.utc) + timedelta(days=days)
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    return payload


def require_auth(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Authorization header required")
    payload = decode_token(creds.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Access token required")
    return payload


def require_admin(payload: dict = Depends(require_auth)) -> dict:
    if payload.get("role") not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin role required")
    return payload


def require_internal_auth(x_internal_auth: str | None = Header(default=None, alias="X-Internal-Auth")) -> None:
    if x_internal_auth != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Internal authentication required")


def _rate_limited(request: Request, bucket: str, limit: int, window_seconds: int) -> None:
    client_ip = request.client.host if request.client else "unknown"
    key = (client_ip, bucket)
    now = datetime.now(timezone.utc)
    window = timedelta(seconds=window_seconds)

    with _rate_lock:
        entries = _rate_windows[key]
        while entries and now - entries[0] > window:
            entries.popleft()
        if len(entries) >= limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        entries.append(now)


def _seed_defaults(db: Session) -> None:
    edge_org = db.query(Organization).filter(Organization.name == DEFAULT_EDGE_ORG_NAME).first()
    if not edge_org:
        edge_org = Organization(name=DEFAULT_EDGE_ORG_NAME, plan="free")
        db.add(edge_org)
        db.flush()

    edge_fp = fingerprint_key(DEFAULT_EDGE_API_KEY)
    if not db.query(ApiKey).filter(ApiKey.key_fingerprint == edge_fp).first():
        raw_hash = bcrypt.hashpw(DEFAULT_EDGE_API_KEY.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        db.add(
            ApiKey(
                key_hash=raw_hash,
                key_fingerprint=edge_fp,
                device_id="edge-planet-1",
                org_id=edge_org.id,
                name="Default edge key",
            )
        )

    db.commit()


def _migrate_schema() -> None:
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("users")}
    ddl: list[str] = []
    if "email_verified" not in columns:
        ddl.append("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE")
    if "otp_code" not in columns:
        ddl.append("ALTER TABLE users ADD COLUMN otp_code VARCHAR")
    if "otp_expires_at" not in columns:
        ddl.append("ALTER TABLE users ADD COLUMN otp_expires_at TIMESTAMP")
    if not ddl:
        return

    with engine.begin() as conn:
        for statement in ddl:
            conn.execute(text(statement))


def _generate_otp() -> str:
    return f"{random.randint(0, 999999):06d}"


def _send_otp_email(email: str, otp_code: str) -> bool:
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
        print(f"[auth-service] OTP fallback email={email} otp={otp_code}")
        return False

    msg = EmailMessage()
    msg["Subject"] = "Your Galaxy OTP Code"
    msg["From"] = SMTP_FROM
    msg["To"] = email
    msg.set_content(
        f"Your Galaxy verification code is {otp_code}. It expires in {OTP_TTL_MINUTES} minutes."
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)
    return True


@app.on_event("startup")
def startup() -> None:
    _migrate_schema()
    with SessionLocal() as db:
        _seed_defaults(db)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "auth"}


@app.post("/auth/register", response_model=RegisterResponse)
def register(req: RegisterReq, request: Request, db: Session = Depends(get_db)):
    _rate_limited(request, "register", limit=5, window_seconds=60)

    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    org = Organization(name=req.org_name)
    db.add(org)
    db.flush()

    otp_code = _generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)

    user = User(
        email=req.email,
        hashed_password=hash_pw(req.password),
        org_id=org.id,
        role="admin",
        is_active=False,
        email_verified=False,
        otp_code=otp_code,
        otp_expires_at=expires_at,
    )
    db.add(user)
    db.commit()

    sent_via_smtp = _send_otp_email(req.email, otp_code)
    return RegisterResponse(
        message="OTP sent to email",
        requires_otp=True,
        dev_otp=None if sent_via_smtp else otp_code,
    )


@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginReq, request: Request, db: Session = Depends(get_db)):
    _rate_limited(request, "login", limit=10, window_seconds=60)

    user = db.query(User).filter(User.email == req.email, User.is_active == True).first()
    if not user or not verify_pw(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Email not verified")

    token_data = {"sub": user.id, "org_id": user.org_id, "role": user.role, "email": user.email}
    return TokenResponse(
        access_token=make_token(token_data, minutes=ACCESS_EXP_MIN),
        refresh_token=make_token(token_data, days=REFRESH_EXP_DAYS, token_type="refresh"),
        user_id=user.id,
        org_id=user.org_id,
        role=user.role,
    )


@app.post("/auth/verify-otp", response_model=TokenResponse)
def verify_otp(req: VerifyOtpReq, request: Request, db: Session = Depends(get_db)):
    _rate_limited(request, "verify-otp", limit=10, window_seconds=60)

    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.email_verified:
        raise HTTPException(status_code=409, detail="Email already verified")
    if not user.otp_code or not user.otp_expires_at:
        raise HTTPException(status_code=400, detail="OTP not generated")
    if datetime.utcnow() > user.otp_expires_at:
        raise HTTPException(status_code=400, detail="OTP expired")
    if req.otp.strip() != user.otp_code:
        raise HTTPException(status_code=401, detail="Invalid OTP")

    user.email_verified = True
    user.is_active = True
    user.otp_code = None
    user.otp_expires_at = None
    db.commit()

    token_data = {"sub": user.id, "org_id": user.org_id, "role": user.role, "email": user.email}
    return TokenResponse(
        access_token=make_token(token_data, minutes=ACCESS_EXP_MIN),
        refresh_token=make_token(token_data, days=REFRESH_EXP_DAYS, token_type="refresh"),
        user_id=user.id,
        org_id=user.org_id,
        role=user.role,
    )


@app.post("/auth/resend-otp", response_model=RegisterResponse)
def resend_otp(req: ResendOtpReq, request: Request, db: Session = Depends(get_db)):
    _rate_limited(request, "resend-otp", limit=5, window_seconds=60)

    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.email_verified:
        raise HTTPException(status_code=409, detail="Email already verified")

    user.otp_code = _generate_otp()
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)
    db.commit()

    sent_via_smtp = _send_otp_email(user.email, user.otp_code)
    return RegisterResponse(
        message="OTP sent to email",
        requires_otp=True,
        dev_otp=None if sent_via_smtp else user.otp_code,
    )


@app.post("/auth/refresh")
def refresh(creds: HTTPAuthorizationCredentials = Depends(security)):
    if not creds:
        raise HTTPException(status_code=401, detail="Authorization header required")
    payload = decode_token(creds.credentials)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token required")
    token_data = {k: v for k, v in payload.items() if k not in ("exp", "type")}
    return {"access_token": make_token(token_data, minutes=ACCESS_EXP_MIN), "token_type": "bearer"}


@app.post("/auth/api-keys")
def create_api_key(req: CreateApiKeyReq, payload: dict = Depends(require_auth), db: Session = Depends(get_db)):
    raw_key = f"gal_{uuid.uuid4().hex}{uuid.uuid4().hex}"
    db.add(
        ApiKey(
            key_hash=bcrypt.hashpw(raw_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            key_fingerprint=fingerprint_key(raw_key),
            device_id=req.device_id,
            org_id=payload["org_id"],
            name=req.name,
        )
    )
    db.commit()
    return {
        "api_key": raw_key,
        "device_id": req.device_id,
        "warning": "Store this key now — it will never be shown again.",
    }


@app.get("/auth/api-keys")
def list_api_keys(payload: dict = Depends(require_admin), db: Session = Depends(get_db)):
    keys = db.query(ApiKey).filter(ApiKey.org_id == payload["org_id"]).all()
    return [
        {
            "id": key.id,
            "device_id": key.device_id,
            "name": key.name,
            "is_active": key.is_active,
            "created_at": str(key.created_at),
        }
        for key in keys
    ]


@app.delete("/auth/api-keys/{key_id}")
def revoke_api_key(key_id: str, payload: dict = Depends(require_admin), db: Session = Depends(get_db)):
    key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.org_id == payload["org_id"]).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    key.is_active = False
    db.commit()
    return {"revoked": key_id}


@app.get("/auth/me")
def me(payload: dict = Depends(require_auth)):
    return payload


@app.post("/internal/api-keys/resolve")
def resolve_api_key(req: ApiKeyResolveRequest, _: None = Depends(require_internal_auth), db: Session = Depends(get_db)):
    fingerprint = fingerprint_key(req.api_key)
    key = db.query(ApiKey).filter(ApiKey.key_fingerprint == fingerprint, ApiKey.is_active == True).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"org_id": key.org_id, "device_id": key.device_id, "key_id": key.id, "name": key.name}