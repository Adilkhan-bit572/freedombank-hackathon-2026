from fastapi import APIRouter, HTTPException, status

from ..db import SessionDep
from ..evaluation.criteria import ChecklistError
from ..evaluation.store import active_checklist, default_checklist, is_default, save_checklist
from ..models import Checklist, ChecklistRead, ChecklistWrite

router = APIRouter(prefix="/checklist", tags=["checklist"])


def _read(c: Checklist) -> ChecklistRead:
    return ChecklistRead(
        id=c.id, criteria=c.criteria, general_rules=c.general_rules, created_at=c.created_at, is_default=is_default(c)
    )


@router.get("", response_model=ChecklistRead)
def get_checklist(session: SessionDep):
    """The active checklist (criteria used for new evaluations)."""
    return _read(active_checklist(session))


@router.put("", response_model=ChecklistRead)
def update_checklist(payload: ChecklistWrite, session: SessionDep):
    """Save a new checklist version. Existing evaluations keep the version they were made with."""
    try:
        return _read(save_checklist(session, payload.criteria, payload.general_rules))
    except ChecklistError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e


@router.post("/reset", response_model=ChecklistRead)
def reset_checklist(session: SessionDep):
    """Restore the hackathon's default checklist (as a new version)."""
    return _read(save_checklist(session, *default_checklist()))
