from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from ..db import SessionDep
from ..evaluation.store import latest_evaluations
from ..models import (
    Appeal,
    Conversation,
    ConversationRead,
    ConversationSummary,
    ConversationUpload,
    UploadResult,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSummary])
def list_conversations(session: SessionDep, evaluated: bool | None = None):
    query = select(Conversation).order_by(Conversation.conversation_id)
    if evaluated is not None:
        query = query.where(Conversation.evaluated == evaluated)
    convos = session.exec(query).all()
    latest = latest_evaluations(session, [c.conversation_id for c in convos])
    appeals = {}  # conversation_id -> status of its newest appeal
    for a in session.exec(select(Appeal.conversation_id, Appeal.status).order_by(Appeal.id)).all():
        appeals[a[0]] = a[1]
    summaries = []
    for c in convos:
        e = latest.get(c.conversation_id)
        summaries.append(
            ConversationSummary(
                conversation_id=c.conversation_id,
                channel=c.channel,
                language=c.language,
                evaluated=c.evaluated,
                status=e.status if e else None,
                final_score=e.final_score if e else None,
                critical_flag=e.critical_flag if e else False,
                appeal_status=appeals.get(c.conversation_id),
                transcript_length=len(c.transcript),
            )
        )
    return summaries


@router.post("", response_model=UploadResult, status_code=status.HTTP_201_CREATED)
def upload_conversations(payload: ConversationUpload, session: SessionDep):
    records = payload.data.records
    ids = [r.conversation_id for r in records]
    existing = set(
        session.exec(
            select(Conversation.conversation_id).where(Conversation.conversation_id.in_(ids))
        ).all()
    )

    created: list[str] = []
    skipped: list[str] = []
    for rec in records:
        if rec.conversation_id in existing:
            skipped.append(rec.conversation_id)
            continue
        session.add(Conversation(**rec.model_dump(), evaluated=False))
        existing.add(rec.conversation_id)  # also skip duplicates within this upload
        created.append(rec.conversation_id)

    session.commit()
    return UploadResult(created=created, skipped=skipped)


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(conversation_id: str, session: SessionDep):
    convo = session.get(Conversation, conversation_id)
    if not convo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return convo
