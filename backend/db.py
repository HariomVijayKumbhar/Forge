from datetime import datetime, timezone
from typing import Optional, List, Any
import json
from sqlmodel import SQLModel, Field, create_engine, Session, select
from backend.config import settings


class Run(SQLModel, table=True):
    __tablename__ = "runs"

    id: str = Field(primary_key=True, index=True)
    user_id: Optional[str] = Field(default=None, index=True)
    repo_url: str
    task: str
    status: str = Field(default="idle")
    provider_used: Optional[str] = None
    files_changed: Optional[str] = Field(default="[]")
    diff: Optional[str] = None
    tests_passed: Optional[bool] = None
    confidence: Optional[int] = Field(default=None)
    summary: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    def get_files_changed(self) -> List[str]:
        if not self.files_changed:
            return []
        try:
            return json.loads(self.files_changed)
        except Exception:
            return []

    def set_files_changed(self, files: List[str]):
        self.files_changed = json.dumps(files)


class Step(SQLModel, table=True):
    __tablename__ = "steps"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    step_index: int
    action_type: str
    tool_name: Optional[str] = None
    tool_input: Optional[str] = None
    tool_output: Optional[str] = None
    status: str = Field(default="ok")
    provider_used: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    event_type: str
    actor_ip: Optional[str] = None
    run_id: Optional[str] = Field(default=None, index=True)
    details: Optional[str] = None
    status: str = Field(default="success")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RevokedToken(SQLModel, table=True):
    __tablename__ = "revoked_tokens"

    jti: str = Field(primary_key=True)
    revoked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(primary_key=True, index=True)
    username: str = Field(unique=True, index=True)
    email: Optional[str] = Field(default=None, index=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def get_normalized_database_url() -> str:
    raw_url = (settings.DATABASE_URL or settings.SQLITE_PATH or "sqlite:///forge.db").strip()
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+psycopg://", 1)
    if raw_url.startswith("postgresql://") and not raw_url.startswith("postgresql+"):
        return raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    # Keep existing psycopg2 URLs working while using the Python 3-compatible
    # driver declared in requirements.txt.
    if raw_url.startswith("postgresql+psycopg2://"):
        return raw_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    return raw_url


def is_postgres() -> bool:
    url = get_normalized_database_url()
    return url.startswith("postgresql")


def get_db_type() -> str:
    return "supabase_postgres" if is_postgres() else "sqlite"


db_url = get_normalized_database_url()

if is_postgres():
    # Explicit TLS: Supabase requires an encrypted connection, and Render's
    # PostgreSQL clients default to "prefer", which is not guaranteed.
    engine = create_engine(
        db_url,
        echo=settings.SQL_ECHO,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=10,
        max_overflow=20,
        connect_args={"sslmode": "require"},
    )
else:
    connect_args = {"check_same_thread": False}
    engine = create_engine(db_url, echo=settings.SQL_ECHO, connect_args=connect_args)


def init_db():
    SQLModel.metadata.create_all(engine)
    _ensure_column(engine, "runs", "user_id", "VARCHAR(255)")


def _ensure_column(engine, table: str, column: str, ddl_type: str):
    """Add a column to an existing table if it does not exist yet.

    SQLModel.metadata.create_all only creates missing tables, not missing
    columns, so schema evolution needs this small migration helper.
    """
    from sqlalchemy import text, inspect

    inspector = inspect(engine)
    if column in [c["name"] for c in inspector.get_columns(table)]:
        return
    with engine.begin() as conn:
        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl_type}'))
        conn.execute(text(f'CREATE INDEX IF NOT EXISTS ix_runs_{column} ON "{table}" ("{column}")'))


def get_session():
    with Session(engine) as session:
        yield session
