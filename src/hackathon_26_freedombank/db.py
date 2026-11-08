from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from .config import DATABASE_URL, DB_ECHO

# check_same_thread=False lets FastAPI's threadpool share the SQLite connection
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=DB_ECHO, connect_args=connect_args)


def _add_missing_columns() -> None:
    """Minimal migration: `create_all` creates new tables but never alters existing ones,
    so add columns that were introduced after a table was created (all nullable / defaulted)."""
    db = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not db.has_table(table.name):
                continue
            existing = {c["name"] for c in db.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl = col.type.compile(dialect=engine.dialect)
                default = ""
                if not col.nullable:  # SQLite needs a default to add a NOT NULL column
                    value = col.default.arg if col.default is not None and not callable(col.default.arg) else None
                    default = f" NOT NULL DEFAULT {value!r}" if isinstance(value, (int, float, str)) else ""
                    if isinstance(value, bool):
                        default = f" NOT NULL DEFAULT {int(value)}"
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl}{default}'))


def init_db() -> None:
    from . import models  # noqa: F401  (register tables on SQLModel.metadata)

    SQLModel.metadata.create_all(engine)
    _add_missing_columns()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
