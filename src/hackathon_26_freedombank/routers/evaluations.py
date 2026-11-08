import csv
import io
from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlmodel import select

from .. import config
from ..db import SessionDep
from ..evaluation.criteria import STANDARD_IDS, enabled_criteria
from ..evaluation.results import build_results, validate_results
from ..evaluation.service import error_result, evaluate_conversation
from ..evaluation.store import (
    active_checklist,
    evaluation_definitions,
    latest_evaluation,
    latest_evaluations,
    standard_criteria,
)
from ..llm import LLMClient, LLMError, get_llm_client
from ..models import Conversation, Evaluation, EvaluationRead

router = APIRouter(tags=["evaluations"])


def get_llm_factory() -> Callable[[str | None], LLMClient]:
    """Dependency so tests can swap in a fake LLM."""
    return get_llm_client


LLMFactoryDep = Annotated[Callable[[str | None], LLMClient], Depends(get_llm_factory)]


@router.post("/conversations/{conversation_id}/evaluate", response_model=EvaluationRead)
def evaluate(
    conversation_id: str,
    session: SessionDep,
    llm_factory: LLMFactoryDep,
    provider: Literal["gemini", "ollama"] | None = None,  # overrides LLM_PROVIDER from .env
):
    """Evaluate with the active checklist. Failures are stored too (status="error"),
    so they show up in results.json instead of disappearing."""
    convo = session.get(Conversation, conversation_id)
    if not convo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    checklist = active_checklist(session)

    # Plain `def` endpoint: FastAPI runs it in a threadpool, so the blocking LLM call is fine.
    try:
        result = evaluate_conversation(
            convo.transcript, checklist.criteria, checklist.general_rules,
            lambda: llm_factory(provider), convo.language,
        )
    except LLMError as e:
        if e.retryable:  # rate limit etc.: don't store, let the client retry later
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(e)) from e
        result = error_result(str(e), provider or config.LLM_PROVIDER, definitions=enabled_criteria(checklist.criteria))

    evaluation = Evaluation(
        conversation_id=conversation_id,
        checklist_id=checklist.id,
        definitions=result.definitions,
        status=result.status,
        error=result.error,
        provider=result.provider,
        model=result.model,
        criteria=result.criteria,
        final_score=result.final_score,
        critical_flag=result.critical_flag,
    )
    convo.evaluated = True
    session.add(evaluation)
    session.add(convo)
    session.commit()
    session.refresh(evaluation)
    return to_read(session, evaluation)


def to_read(session, evaluation: Evaluation) -> EvaluationRead:
    """EvaluationRead with `definitions` filled in for evaluations stored before the snapshot existed."""
    data = evaluation.model_dump()
    data["definitions"] = evaluation_definitions(session, evaluation)
    return EvaluationRead.model_validate(data)


@router.get("/conversations/{conversation_id}/evaluation", response_model=EvaluationRead)
def get_evaluation(conversation_id: str, session: SessionDep):
    evaluation = latest_evaluation(session, conversation_id)
    if not evaluation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation has no evaluation")
    return to_read(session, evaluation)


NON_STANDARD_ERROR = "Оценено нестандартным набором критериев — для results.json переоцените стандартными 8."


@router.get("/evaluations/results.json")
def export_results(session: SessionDep, download: bool = True):
    """Every conversation's latest evaluation in the hackathon results format (schema 1.0).
    Conversations that were never evaluated, or were evaluated with a criteria set other than
    the standard 8, are listed with status="error"."""
    ids = session.exec(select(Conversation.conversation_id).order_by(Conversation.conversation_id)).all()
    latest = latest_evaluations(session)
    items, non_standard = [], 0
    for cid in ids:
        ev = latest.get(cid)
        if ev is not None and ev.status == "ok" and sorted(c["criterion_id"] for c in ev.criteria) != sorted(STANDARD_IDS):
            ev, non_standard = error_result(NON_STANDARD_ERROR, ev.provider, ev.model), non_standard + 1
        items.append((cid, ev))
    doc = build_results(config.TEAM_NAME, items)
    problems = validate_results(doc, standard_criteria())
    headers = {"X-Validation-Problems": str(len(problems)), "X-Non-Standard": str(non_standard)}
    if download:
        headers["Content-Disposition"] = 'attachment; filename="results.json"'
    return JSONResponse(doc, headers=headers)


def _cell_value(c: dict) -> str:
    v = c.get("value")
    if v is None:
        return "N/A"
    if c["kind"] == "scale":
        return str(v)
    return "Да" if v is True else "Нет"


def _safe(text) -> str:
    """Stop spreadsheet apps from treating LLM text as a formula."""
    s = str(text)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


@router.get("/evaluations/export.csv", response_class=Response)
def export_csv(session: SessionDep):
    """Latest evaluation of every conversation as a CSV (Excel-friendly: ';' + UTF-8 BOM)."""
    latest = latest_evaluations(session)
    convos = session.exec(select(Conversation).where(Conversation.conversation_id.in_(list(latest)))).all()
    channels = {c.conversation_id: c.channel for c in convos}

    ids = [c["id"] for c in active_checklist(session).criteria]
    for e in latest.values():  # criteria from older checklist versions go at the end
        ids += [c["criterion_id"] for c in e.criteria if c["criterion_id"] not in ids]

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(
        ["conversation_id", "channel", "status", "final_score", "critical_flag", "провайдер", "модель", "ошибка"]
        + ids
        + [f"обоснование {i}" for i in ids]
    )
    for cid in sorted(latest):
        e = latest[cid]
        by_id = {c["criterion_id"]: c for c in e.criteria}
        w.writerow(
            [cid, channels.get(cid, ""), e.status, "" if e.final_score is None else e.final_score,
             "Да" if e.critical_flag else "Нет", e.provider, e.model, _safe(e.error or "")]
            + [_cell_value(by_id[i]) if i in by_id else "" for i in ids]
            + [_safe(by_id[i].get("rationale", "")) if i in by_id else "" for i in ids]
        )
    return Response(
        content="﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="call-qa-results.csv"'},
    )
