from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, Integer, Text, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# Database URL from environment or default for development
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/galaxy"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Event(Base):
    """Stores detection events from edge planets."""
    __tablename__ = "events"

    id = Column(String(36), primary_key=True)  # UUID
    tenant_id = Column(String(36), nullable=False, index=True)
    device_id = Column(String(255), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)  # "fire", "smoke", "intrusion", etc.
    confidence = Column(Float, nullable=False)
    frame_hash = Column(LargeBinary, nullable=True)
    signature = Column(LargeBinary, nullable=True)  # Device signature
    location = Column(String(255), nullable=True)
    verified = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Tenant(Base):
    """Represents a customer/organization."""
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True)  # UUID
    name = Column(String(255), nullable=False)
    api_key = Column(String(255), unique=True, nullable=False, index=True)
    balance = Column(Float, default=1000.0)  # Credit balance
    quota_events_per_day = Column(Integer, default=10000)
    events_today = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Device(Base):
    """Represents an edge planet."""
    __tablename__ = "devices"

    id = Column(String(255), primary_key=True)  # Device ID
    tenant_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    device_type = Column(String(100), default="jetson")  # jetson, coral, hailo
    location = Column(String(255), nullable=True)
    public_key = Column(Text, nullable=True)  # For signature verification
    status = Column(String(50), default="offline")  # online, offline, error
    last_heartbeat = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# Create all tables
def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for FastAPI to provide DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
