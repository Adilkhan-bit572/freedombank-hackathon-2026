from sqlmodel import Session, func, select

from ..models import Checklist, Evaluation
from .criteria import DEFAULT_CRITERIA, DEFAULT_GENERAL_RULES, STANDARD_IDS, enabled_criteria, normalise_criteria


def latest_evaluations(session: Session, conversation_ids: list[str] | None = None) -> dict[str, Evaluation]:
    """Newest evaluation per conversation (ids are monotonic, so max(id) = newest)."""
    newest = select(func.max(Evaluation.id)).group_by(Evaluation.conversation_id)
    if conversation_ids is not None:
        newest = newest.where(Evaluation.conversation_id.in_(conversation_ids))
    rows = session.exec(select(Evaluation).where(Evaluation.id.in_(newest))).all()
    return {e.conversation_id: e for e in rows}


def latest_evaluation(session: Session, conversation_id: str) -> Evaluation | None:
    return session.exec(
        select(Evaluation)
        .where(Evaluation.conversation_id == conversation_id)
        .order_by(Evaluation.id.desc())
        .limit(1)
    ).first()


def default_checklist() -> tuple[list[dict], str]:
    return normalise_criteria(DEFAULT_CRITERIA), DEFAULT_GENERAL_RULES


def standard_criteria() -> list[dict]:
    """The 8 criteria of the hackathon results format, enabled (used by the export)."""
    return [{**c, "enabled": True} for c in default_checklist()[0] if c["id"] in STANDARD_IDS]


def save_checklist(session: Session, criteria: list[dict], general_rules: str) -> Checklist:
    """Validate (raises ChecklistError) and store a new active checklist version."""
    checklist = Checklist(criteria=normalise_criteria(criteria), general_rules=general_rules.strip())
    session.add(checklist)
    session.commit()
    session.refresh(checklist)
    return checklist


def active_checklist(session: Session) -> Checklist:
    """Newest checklist version; seeds the default one on first use."""
    checklist = session.exec(select(Checklist).order_by(Checklist.id.desc()).limit(1)).first()
    if checklist is None:
        checklist = save_checklist(session, *default_checklist())
    elif not any("visible" in c for c in checklist.criteria):
        # Saved before the catalog fields existed: keep it, add default criteria it lacks (e.g. pushback).
        have = {c["id"] for c in checklist.criteria}
        extra = [c for c in default_checklist()[0] if c["id"] not in have]
        checklist = save_checklist(session, checklist.criteria + extra, checklist.general_rules)
    return checklist


def evaluation_definitions(session: Session, evaluation: Evaluation) -> list[dict]:
    """Criteria definitions an evaluation was made with (snapshot, or its checklist version)."""
    if evaluation.definitions:
        return evaluation.definitions
    checklist = session.get(Checklist, evaluation.checklist_id) if evaluation.checklist_id else None
    criteria = checklist.criteria if checklist else default_checklist()[0]
    used = {c["criterion_id"] for c in evaluation.criteria}
    return [c for c in normalise_criteria(criteria) if c["id"] in used] if used else enabled_criteria(criteria)


def is_default(checklist: Checklist) -> bool:
    criteria, rules = default_checklist()
    return checklist.criteria == criteria and checklist.general_rules == rules
