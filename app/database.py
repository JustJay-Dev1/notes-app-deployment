import os
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def build_database_url() -> str:
    """
    Resolve the database URL to connect to.

    Individual POSTGRES_* env vars are read separately (rather than a single
    DATABASE_URL) because in Kubernetes these values typically come from two
    different sources: non-secret connection info (host/port/db) lives in a
    ConfigMap, while the password lives in a Secret created by the database
    subchart. Wiring both into this app's env vars is part of the assignment.
    """
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "notes")
    password = os.getenv("POSTGRES_PASSWORD", "notes")
    db = os.getenv("POSTGRES_DB", "notes")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


DATABASE_URL = build_database_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def wait_for_db(retries: int = 10, delay_seconds: float = 2.0) -> None:
    """Best-effort wait so the app doesn't crash-loop while Postgres boots."""
    last_error = None
    for _ in range(retries):
        try:
            with engine.connect():
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(delay_seconds)
    raise RuntimeError(f"Database not reachable: {last_error}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
