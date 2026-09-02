import hashlib
import hmac
import logging
import os
import secrets
import smtplib
import threading
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import bcrypt
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Boolean, Column, DateTime, String, create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from shared.security import configure_cors, environment, jwt_audience, jwt_issuer, required_secret

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("galaxy-auth")

_is_production = environment() == "production"
app = FastAPI(
    title="Galaxy Auth Service",
    version="2.1.0",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
)
configure_cors(app)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/galaxy")
ACCESS_EXP_MIN = int(os.getenv("ACCESS_EXP_MIN", "15"))
REFRESH_EXP_DAYS = int(os.getenv("REFRESH_EXP_DAYS", "7"))
DEFAULT_EDGE_ORG_NAME = os.getenv("DEFAULT_EDGE_ORG_NAME", "Edge Devices").strip() or "Edge Devices"
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@galaxy.local").strip()
OTP_TTL_MINUTES = int(os.getenv("OTP_TTL_MINUTES", "10"))
REGISTRATION_ENABLED = os.getenv(
    "AUTH_REGISTRATION_ENABLED", "false" if _is_production else "true"
).lower() in {"1", "true", "yes"}
ALLOW_DEV_OTP = (
    not _is_production
    and os.getenv("AUTH_ALLOW_DEV_OTP", "false").lower() in {"1", "true", "yes"}
)
BOOTSTRAP_EDGE_KEY = os.getenv("BOOTSTRAP_EDGE_API_KEY", "").strip()
BOOTSTRAP_EDGE_ENABLED = os.getenv("AUTH_BOOTSTRAP_EDGE_KEY", "false").lower() in {
    "1",
    "true",
    "yes",
}

if ACCESS_EXP_MIN < 5 or ACCESS_EXP_MIN > 120:
    raise RuntimeError("ACCESS_EXP_MIN must be between 5 and 120")
if REFRESH_EXP_DAYS < 1 or REFRESH_EXP_DAYS > 30:
    raise RuntimeError("REFRESH_EXP_DAYS must be between 1 and 30")
if OTP_TTL_MINUTES < 3 or OTP_TTL_MINUTES > 30:
    raise RuntimeError("OTP_TTL_MINUTES must be between 3 and 30")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
security = HTTPBearer(auto_error=False)

_rate_lock = threading.Lock()
_rate_windows: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)
_MAX_RATE_BUCKETS = int(os.getenv("AUTH_MAX_RATE_BUCKETS", "10000"))


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
    key_hash = Column(String, unique=True, nullable=False)
    key_fingerprint = Column(String, unique=True, nullable=False, index=True)
    device_id = Column(String, nullable=False)
    org_id = Column(String, nullable=False, index=True)
    name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RegisterReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    org_name: str = Field(min_length=1, max_length=120)


class LoginReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class VerifyOtpReq(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")


class ResendOtpReq(BaseModel):
    email: EmailStr


class RegisterResponse(BaseModel):
    message: str
    requires_otp: bool = True
    dev_otp: str | None = None


class CreateApiKeyReq(BaseModel):
    device_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=120)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    org_id: str
    role: str


class ApiKeyResolveRequest(BaseModel):
    api_key: str = Field(min_length=24, max_length=256)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/auth/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_pw(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def fingerprint_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _token_secret() -> str:
    return required_secret("JWT_SECRET")


def make_token(
    data: dict,
    *,
    minutes: int | None = None,
    days: int | None = None,
    token_type: str = "access",
) -> str:
    now = datetime.now(timezone.utc)
    if minutes is not None:
        expires_at = now + timedelta(minutes=minutes)
    elif days is not None:
        expires_at = now + timedelta(days=days)
    else:
        raise ValueError("token expiry is required")

    payload = {
        **data,
        "type": token_type,
        "iss": jwt_issuer(),
        "aud": jwt_audience(),
        "iat": now,
        "nbf": now - timedelta(seconds=1),
        "exp": expires_at,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _token_secret(), algorithm="HS256")


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            _token_secret(),
            algorithms=["HS256"],
            issuer=jwt_issuer(),
            audience=jwt_audience(),
            options={
                "require": ["exp", "iat", "jti", "iss", "aud", "sub", "org_id", "type"]
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=401, detail=f"{expected_type.title()} token required")
    return payload


def require_auth(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Authorization header required")
    return decode_token(creds.credentials, "access")


def require_admin(payload: dict = Depends(require_auth)) -> dict:
    if payload.get("role") not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin role required")
    return payload


def require_internal_auth(
    x_internal_auth: str | None = Header(default=None, alias="X-Internal-Auth"),
) -> None:
    expected = required_secret("INTERNAL_API_KEY")
    supplied = x_internal_auth or ""
    if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Internal authentication required")


def _rate_limited(request: Request, bucket: str, limit: int, window_seconds: int) -> None:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    client_ip = forwarded_for or (request.client.host if request.client else "unknown")
    key = (client_ip[:64], bucket)
    now = datetime.now(timezone.utc)
    window = timedelta(seconds=window_seconds)

    with _rate_lock:
        if key not in _rate_windows and len(_rate_windows) >= _MAX_RATE_BUCKETS:
            stale = [item for item, entries in _rate_windows.items() if not entries or now - entries[-1] > window]
            for item in stale[: max(1, len(stale))]:
                _rate_windows.pop(item, None)
            if len(_rate_windows) >= _MAX_RATE_BUCKETS:
                raise HTTPException(status_code=503, detail="Authentication service busy")

        entries = _rate_windows[key]
        while entries and now - entries[0] > window:
            entries.popleft()
        if len(entries) >= limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        entries.append(now)


def _otp_digest(email: str, otp_code: str) -> str:
    message = f"{_normalize_email(email)}:{otp_code}".encode("utf-8")
    return hmac.new(_token_secret().encode("utf-8"), message, hashlib.sha256).hexdigest()


def _seed_edge_key(db: Session) -> None:
    if not BOOTSTRAP_EDGE_ENABLED:
        return
    if not BOOTSTRAP_EDGE_KEY:
        raise RuntimeError("BOOTSTRAP_EDGE_API_KEY is required when AUTH_BOOTSTRAP_EDGE_KEY=true")
    required_secret("BOOTSTRAP_EDGE_API_KEY", minimum_length=24)

    edge_org = db.query(Organization).filter(Organization.name == DEFAULT_EDGE_ORG_NAME).first()
    if not edge_org:
        edge_org = Organization(name=DEFAULT_EDGE_ORG_NAME, plan="free")
        db.add(edge_org)
        db.flush()

    edge_fp = fingerprint_key(BOOTSTRAP_EDGE_KEY)
    if not db.query(ApiKey).filter(ApiKey.key_fingerprint == edge_fp).first():
        raw_hash = bcrypt.hashpw(
            BOOTSTRAP_EDGE_KEY.encode("utf-8"), bcrypt.gensalt(rounds=12)
        ).decode("utf-8")
        db.add(
            ApiKey(
                key_hash=raw_hash,
                key_fingerprint=edge_fp,
                device_id=os.getenv("BOOTSTRAP_EDGE_DEVICE_ID", "edge-planet-1"),
                org_id=edge_org.id,
                name="Bootstrap edge key",
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
    with engine.begin() as conn:
        for statement in ddl:
            conn.execute(text(statement))


def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD and SMTP_FROM)


def _send_otp_email(email: str, otp_code: str) -> bool:
    if not _smtp_configured():
        return False

    msg = EmailMessage()
    msg["Subject"] = "Your Galaxy verification code"
    msg["From"] = SMTP_FROM
    msg["To"] = email
    msg.set_content(
        f"Your Galaxy verification code is {otp_code}. "
        f"It expires in {OTP_TTL_MINUTES} minutes."
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)
    return True


def _issue_tokens(user: User) -> TokenResponse:
    token_data = {
        "sub": user.id,
        "org_id": user.org_id,
        "role": user.role,
        "email": user.email,
    }
    return TokenResponse(
        access_token=make_token(token_data, minutes=ACCESS_EXP_MIN),
        refresh_token=make_token(
            token_data, days=REFRESH_EXP_DAYS, token_type="refresh"
        ),
        user_id=user.id,
        org_id=user.org_id,
        role=user.role,
    )


@app.on_event("startup")
def startup() -> None:
    required_secret("JWT_SECRET")
    required_secret("INTERNAL_API_KEY")
    Base.metadata.create_all(bind=engine)
    _migrate_schema()
    with SessionLocal() as db:
        _seed_edge_key(db)
    logger.info(
        "auth service started registration_enabled=%s smtp_configured=%s",
        REGISTRATION_ENABLED,
        _smtp_configured(),
    )


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "auth"}


@app.post("/auth/register", response_model=RegisterResponse)
def register(req: RegisterReq, request: Request, db: Session = Depends(get_db)):
    _rate_limited(request, "register", limit=5, window_seconds=300)
    if not REGISTRATION_ENABLED:
        raise HTTPException(status_code=403, detail="Registration is disabled")
    if _is_production and not _smtp_configured():
        raise HTTPException(status_code=503, detail="Email verification is unavailable")

    email = _normalize_email(str(req.email))
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    org = Organization(name=req.org_name.strip())
    db.add(org)
    db.flush()

    otp_code = _generate_otp()
    user = User(
        email=email,
        hashed_password=hash_pw(req.password),
        org_id=org.id,
        role="admin",
        is_active=False,
        email_verified=False,
        otp_code=_otp_digest(email, otp_code),
        otp_expires_at=datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.add(user)
    db.commit()

    try:
        sent_via_smtp = _send_otp_email(email, otp_code)
    except (OSError, smtplib.SMTPException) as exc:
        logger.warning("OTP delivery failed for user_id=%s: %s", user.id, type(exc).__name__)
        sent_via_smtp = False

    if not sent_via_smtp and not ALLOW_DEV_OTP:
        raise HTTPException(status_code=503, detail="Email verification is unavailable")

    return RegisterResponse(
        message="If delivery is available, a verification code has been sent.",
        dev_otp=otp_code if ALLOW_DEV_OTP else None,
    )


@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginReq, request: Request, db: Session = Depends(get_db)):
    _rate_limited(request, "login", limit=10, window_seconds=300)
    email = _normalize_email(str(req.email))
    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user or not verify_pw(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Email not verified")
    return _issue_tokens(user)


@app.post("/auth/verify-otp", response_model=TokenResponse)
def verify_otp(req: VerifyOtpReq, request: Request, db: Session = Depends(get_db)):
    _rate_limited(request, "verify-otp", limit=8, window_seconds=300)
    email = _normalize_email(str(req.email))
    user = db.query(User).filter(User.email == email).first()
    invalid = (
        not user
        or user.email_verified
        or not user.otp_code
        or not user.otp_expires_at
        or datetime.utcnow() > user.otp_expires_at
        or not hmac.compare_digest(user.otp_code, _otp_digest(email, req.otp))
    )
    if invalid:
        raise HTTPException(status_code=401, detail="Invalid or expired verification code")

    user.email_verified = True
    user.is_active = True
    user.otp_code = None
    user.otp_expires_at = None
    db.commit()
    return _issue_tokens(user)


@app.post("/auth/resend-otp", response_model=RegisterResponse)
def resend_otp(req: ResendOtpReq, request: Request, db: Session = Depends(get_db)):
    _rate_limited(request, "resend-otp", limit=3, window_seconds=300)
    if not REGISTRATION_ENABLED:
        raise HTTPException(status_code=403, detail="Registration is disabled")

    email = _normalize_email(str(req.email))
    user = db.query(User).filter(User.email == email).first()
    dev_otp = None
    if user and not user.email_verified:
        otp_code = _generate_otp()
        user.otp_code = _otp_digest(email, otp_code)
        user.otp_expires_at = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)
        db.commit()
        try:
            sent = _send_otp_email(email, otp_code)
        except (OSError, smtplib.SMTPException):
            sent = False
        if ALLOW_DEV_OTP and not sent:
            dev_otp = otp_code

    return RegisterResponse(
        message="If the account is eligible, a verification code has been sent.",
        dev_otp=dev_otp,
    )


@app.post("/auth/refresh")
def refresh(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    if not creds:
        raise HTTPException(status_code=401, detail="Authorization header required")
    payload = decode_token(creds.credentials, "refresh")
    user = db.query(User).filter(
        User.id == payload.get("sub"),
        User.is_active == True,
        User.email_verified == True,
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="Account is not active")
    token_data = {
        "sub": user.id,
        "org_id": user.org_id,
        "role": user.role,
        "email": user.email,
    }
    return {
        "access_token": make_token(token_data, minutes=ACCESS_EXP_MIN),
        "token_type": "bearer",
    }


@app.post("/auth/api-keys")
def create_api_key(
    req: CreateApiKeyReq,
    payload: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    raw_key = f"gal_{secrets.token_urlsafe(48)}"
    db.add(
        ApiKey(
            key_hash=bcrypt.hashpw(
                raw_key.encode("utf-8"), bcrypt.gensalt(rounds=12)
            ).decode("utf-8"),
            key_fingerprint=fingerprint_key(raw_key),
            device_id=req.device_id.strip(),
            org_id=payload["org_id"],
            name=req.name.strip(),
        )
    )
    db.commit()
    return {
        "api_key": raw_key,
        "device_id": req.device_id,
        "warning": "Store this key now; it will not be shown again.",
    }


@app.get("/auth/api-keys")
def list_api_keys(
    payload: dict = Depends(require_admin), db: Session = Depends(get_db)
):
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
def revoke_api_key(
    key_id: str,
    payload: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    key = db.query(ApiKey).filter(
        ApiKey.id == key_id, ApiKey.org_id == payload["org_id"]
    ).first()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    key.is_active = False
    db.commit()
    return {"revoked": key_id}


@app.get("/auth/me")
def me(payload: dict = Depends(require_auth)):
    return payload


@app.post("/internal/api-keys/resolve")
def resolve_api_key(
    req: ApiKeyResolveRequest,
    _: None = Depends(require_internal_auth),
    db: Session = Depends(get_db),
):
    fingerprint = fingerprint_key(req.api_key)
    key = db.query(ApiKey).filter(
        ApiKey.key_fingerprint == fingerprint, ApiKey.is_active == True
    ).first()
    if not key or not bcrypt.checkpw(
        req.api_key.encode("utf-8"), key.key_hash.encode("utf-8")
    ):
        raise HTTPException(status_code=404, detail="API key not found")
    return {
        "org_id": key.org_id,
        "device_id": key.device_id,
        "key_id": key.id,
        "name": key.name,
    }
