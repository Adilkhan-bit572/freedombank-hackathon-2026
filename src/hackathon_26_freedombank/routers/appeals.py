"""Operator appeals against an evaluation, and the reviewer's answers.

Flow: operator saves a draft (PUT) and sends it (submit) -> reviewer writes comments
(review) -> reviewer either confirms the evaluation (confirm) or asks the AI to re-evaluate
the criteria they commented on (revise), which creates a new evaluation.
"""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from sqlmodel import Session, select

from .. import config
from ..db import SessionDep
from ..evaluation.service import revise_evaluation
from ..evaluation.store import active_checklist, evaluation_definitions, latest_evaluation
from ..llm import LLMError
from ..models import Appeal, AppealRead, AppealReviewWrite, AppealWrite, Conversation, Evaluation, EvaluationRead
from .evaluations import LLMFactoryDep, to_read

router = APIRouter(tags=["appeals"])


def latest_appeal(session: Session, conversation_id: str) -> Appeal | None:
    return session.exec(
        select(Appeal).where(Appeal.conversation_id == conversation_id).order_by(Appeal.id.desc()).limit(1)
    ).first()


def _get(session: Session, appeal_id: int) -> Appeal:
    appeal = session.get(Appeal, appeal_id)
    if not appeal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appeal not found")
    return appeal


def _require(appeal: Appeal, *allowed: str) -> None:
    if appeal.status not in allowed:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Апелляция в статусе «{appeal.status}», действие недоступно.")


def _save(session: Session, appeal: Appeal) -> Appeal:
    appeal.updated_at = datetime.now(UTC)
    session.add(appeal)
    session.commit()
    session.refresh(appeal)
    return appeal


@router.get("/conversations/{conversation_id}/appeal", response_model=AppealRead)
def get_appeal(conversation_id: str, session: SessionDep):
    """The latest appeal of a conversation (any status)."""
    appeal = latest_appeal(session, conversation_id)
    if not appeal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No appeal")
    return appeal


@router.put("/conversations/{conversation_id}/appeal", response_model=AppealRead)
def save_appeal(conversation_id: str, payload: AppealWrite, session: SessionDep):
    """Save the operator's draft («Сохранить обращение»). Creates a new appeal when the latest one
    was already sent or is for an older evaluation."""
    evaluation = session.get(Evaluation, payload.evaluation_id)
    if not evaluation or evaluation.conversation_id != conversation_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluation not found")
    known = {c["criterion_id"] for c in evaluation.criteria}
    items = [
        {"criterion_id": i.criterion_id, "operator_comment": i.operator_comment.strip(), "reviewer_comment": ""}
        for i in payload.items
        if i.criterion_id in known
    ]
    appeal = latest_appeal(session, conversation_id)
    if not appeal or appeal.status != "draft" or appeal.evaluation_id != evaluation.id:
        appeal = Appeal(conversation_id=conversation_id, evaluation_id=evaluation.id, items=items)
    appeal.items = items
    return _save(session, appeal)


@router.post("/appeals/{appeal_id}/submit", response_model=AppealRead)
def submit_appeal(appeal_id: int, session: SessionDep):
    """Send the appeal to the reviewer («Сохранить и отправить»)."""
    appeal = _get(session, appeal_id)
    _require(appeal, "draft")
    if not appeal.items:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Нет оспоренных критериев.")
    empty = [i["criterion_id"] for i in appeal.items if not i["operator_comment"]]
    if empty:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Заполните объяснение: " + ", ".join(empty))
    appeal.status = "submitted"
    return _save(session, appeal)


@router.put("/appeals/{appeal_id}/review", response_model=AppealRead)
def save_review(appeal_id: int, payload: AppealReviewWrite, session: SessionDep):
    """Save the reviewer's comments (only `reviewer_comment` is taken from the payload)."""
    appeal = _get(session, appeal_id)
    _require(appeal, "submitted")
    comments = {i.criterion_id: i.reviewer_comment.strip() for i in payload.items}
    appeal.items = [{**i, "reviewer_comment": comments.get(i["criterion_id"], i["reviewer_comment"])} for i in appeal.items]
    return _save(session, appeal)


@router.post("/appeals/{appeal_id}/confirm", response_model=AppealRead)
def confirm_appeal(appeal_id: int, session: SessionDep, payload: AppealReviewWrite | None = None):
    """The appeal is not upheld: the evaluation stands."""
    appeal = _get(session, appeal_id)
    _require(appeal, "submitted")
    if payload:
        save_review(appeal_id, payload, session)
    appeal.status = "confirmed"
    return _save(session, appeal)


@router.post("/appeals/{appeal_id}/revise", response_model=EvaluationRead)
def revise_appeal(
    appeal_id: int,
    session: SessionDep,
    llm_factory: LLMFactoryDep,
    payload: AppealReviewWrite | None = None,
    provider: Literal["gemini", "ollama"] | None = None,
):
    """Re-evaluate the criteria the reviewer commented on; others keep their results.
    Stores and returns the new evaluation."""
    appeal = _get(session, appeal_id)
    _require(appeal, "submitted")
    if payload:
        save_review(appeal_id, payload, session)
    base = session.get(Evaluation, appeal.evaluation_id)
    convo = session.get(Conversation, appeal.conversation_id)
    if base is None or base.status != "ok":
        raise HTTPException(status.HTTP_409_CONFLICT, "Исходная оценка недоступна для пересмотра.")
    if latest_evaluation(session, convo.conversation_id).id != base.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Диалог уже переоценён после подачи апелляции.")

    definitions = evaluation_definitions(session, base)
    try:
        result = revise_evaluation(
            convo.transcript, definitions, base.criteria, appeal.items,
            active_checklist(session).general_rules, lambda: llm_factory(provider), convo.language,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e
    except LLMError as e:
        code = status.HTTP_429_TOO_MANY_REQUESTS if e.retryable else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(code, str(e)) from e

    revised = Evaluation(
        conversation_id=convo.conversation_id,
        checklist_id=base.checklist_id,
        definitions=definitions,
        parent_evaluation_id=base.id,
        appeal_id=appeal.id,
        status="ok",
        provider=result.provider or config.LLM_PROVIDER,
        model=result.model,
        criteria=result.criteria,
        final_score=result.final_score,
        critical_flag=result.critical_flag,
    )
    session.add(revised)
    session.commit()
    session.refresh(revised)
    appeal.status = "revised"
    appeal.revised_evaluation_id = revised.id
    _save(session, appeal)
    session.refresh(revised)  # the commit above expired it
    return to_read(session, revised)
