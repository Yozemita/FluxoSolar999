import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Owner(Base):
    __tablename__ = "owners"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    peer: Mapped[str] = mapped_column(String(256), index=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Session(Base):
    __tablename__ = "sessions"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"))
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant: Mapped[str] = mapped_column(String(16))
    external_code: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    affiliate_url: Mapped[str] = mapped_column(Text)
    storefront_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MetricEvent(Base):
    __tablename__ = "metric_events"
    event_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    profile_visits: Mapped[int] = mapped_column(Integer, default=0)
    follows: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    commission: Mapped[float] = mapped_column(Float, default=0)
    spend: Mapped[float] = mapped_column(Float, default=0)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Creative(Base):
    __tablename__ = "creatives"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    caption: Mapped[str] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text)
    media_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    creative_id: Mapped[int] = mapped_column(ForeignKey("creatives.id"), index=True)
    channel: Mapped[str] = mapped_column(String(32))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="planned")


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    agent: Mapped[str] = mapped_column(String(32))
    result: Mapped[dict] = mapped_column(JSON)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(100))
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def make_database(url=None):
    url = url or os.getenv("DATABASE_URL")
    if not url:
        if os.getenv("RAILWAY_ENVIRONMENT_ID"):
            raise RuntimeError("Configure DATABASE_URL with the Railway PostgreSQL reference.")
        Path("data").mkdir(exist_ok=True)
        url = "sqlite:///data/growth.db"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    options = {"pool_pre_ping": True, "hide_parameters": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False, "timeout": 30}
    else:
        options["connect_args"] = {"connect_timeout": 5}
    engine = create_engine(url, **options)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine, sessionmaker(engine, expire_on_commit=False)


def get_db(request):
    # Dependency wrappers in main provide the typed FastAPI Request.
    with request.app.state.sessions() as session:
        yield session
