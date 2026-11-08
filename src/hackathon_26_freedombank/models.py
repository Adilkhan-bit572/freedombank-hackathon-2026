from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class ItemBase(SQLModel):
    name: str = Field(index=True, max_length=255)
    description: str | None = None


class Item(ItemBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ItemCreate(ItemBase):
    pass


class ItemRead(ItemBase):
    id: int
    created_at: datetime


class ItemUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
