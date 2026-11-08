from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, SQLModel, create_engine

from .config import DATABASE_URL, DB_ECHO

# check_same_thread=False lets FastAPI's threadpool share the SQLite connection
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=DB_ECHO, connect_args=connect_args)


def init_db() -> None:
    from . import models  # noqa: F401  (register tables on SQLModel.metadata)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
