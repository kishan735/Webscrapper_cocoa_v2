from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings
from app.storage import models  # noqa: F401 -- register tables

settings.db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
