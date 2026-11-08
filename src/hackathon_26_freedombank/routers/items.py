from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from ..db import SessionDep
from ..models import Item, ItemCreate, ItemRead, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(data: ItemCreate, session: SessionDep):
    item = Item.model_validate(data)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("", response_model=list[ItemRead])
def list_items(session: SessionDep, offset: int = 0, limit: int = 100):
    return session.exec(select(Item).offset(offset).limit(min(limit, 100))).all()


@router.get("/{item_id}", response_model=ItemRead)
def get_item(item_id: int, session: SessionDep):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return item


@router.patch("/{item_id}", response_model=ItemRead)
def update_item(item_id: int, data: ItemUpdate, session: SessionDep):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    item.sqlmodel_update(data.model_dump(exclude_unset=True))
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, session: SessionDep):
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    session.delete(item)
    session.commit()
