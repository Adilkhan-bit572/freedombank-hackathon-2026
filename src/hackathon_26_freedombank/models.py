from datetime import UTC, datetime
from typing import Literal

from sqlmodel import JSON, Column, Field, SQLModel

# --- Conversations ---------------------------------------------------------


class TranscriptEntry(SQLModel):
    timestamp: str
    speaker: str
    text: str


class ConversationBase(SQLModel):
    conversation_id: str
    channel: str
    language: str
    audio_url: str | None = None
    transcript: list[TranscriptEntry]


class Conversation(SQLModel, table=True):
    conversation_id: str = Field(primary_key=True)
    channel: str
    language: str
    audio_url: str | None = None
    transcript: list[dict] = Field(sa_column=Column(JSON, nullable=False))
    evaluated: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConversationRead(ConversationBase):
    evaluated: bool
    created_at: datetime


class ConversationRecords(SQLModel):
    total_records: int | None = None
    records: list[ConversationBase]


class ConversationUpload(SQLModel):
    """Matches the data.json format: {"data": {"total_records": ..., "records": [...]}}."""

    data: ConversationRecords


class UploadResult(SQLModel):
    created: list[str]
    skipped: list[str]


# --- Checklist (editable evaluation criteria) ------------------------------


class CriterionDef(SQLModel):
    id: str
    title: str
    kind: Literal["bool", "scale", "critical"]
    nullable: bool = False
    negative: bool = False
    weight: float = 0
    description: str = ""
    levels: list[int] | None = None
    max: int | None = None
    level_descriptions: dict[str, str] | None = None
    visible: bool = True
    enabled: bool = True
    comment: str = ""


class Checklist(SQLModel, table=True):
    """Each save creates a new version; the newest one is active."""

    id: int | None = Field(default=None, primary_key=True)
    criteria: list[dict] = Field(sa_column=Column(JSON, nullable=False))
    general_rules: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChecklistWrite(SQLModel):
    criteria: list[dict]
    general_rules: str = ""


class ChecklistRead(SQLModel):
    id: int
    criteria: list[CriterionDef]
    general_rules: str
    created_at: datetime
    is_default: bool = False


# --- Evaluations -----------------------------------------------------------


class CriterionResult(SQLModel):
    criterion_id: str
    title: str
    kind: str  # "bool" | "scale" | "critical"
    negative: bool = False
    max: int | None = None
    value: bool | int | None = None  # null = N/A
    rationale: str = ""
    evidence_turns: list[int] = []  # 1-based indexes into the conversation transcript
    evidence_kind: str | None = None  # "error" | "missing" | "good" | None
    revised: bool = False  # changed by a reviewer-requested revision


class Evaluation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: str = Field(foreign_key="conversation.conversation_id", index=True)
    checklist_id: int | None = Field(default=None, foreign_key="checklist.id")
    # criteria definitions used (snapshot), so scoring/revisions don't depend on later checklist edits
    definitions: list[dict] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    parent_evaluation_id: int | None = None  # set on a revision: the evaluation it revises
    appeal_id: int | None = None  # set on a revision: the appeal that caused it
    status: str = "ok"  # "ok" | "error"
    error: str | None = None
    provider: str
    model: str
    criteria: list[dict] = Field(sa_column=Column(JSON, nullable=False))
    final_score: float | None = None  # None = error or nothing applicable
    critical_flag: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class EvaluationRead(SQLModel):
    id: int
    conversation_id: str
    checklist_id: int | None
    definitions: list[CriterionDef] | None = None
    parent_evaluation_id: int | None = None
    appeal_id: int | None = None
    status: str
    error: str | None
    provider: str
    model: str
    criteria: list[CriterionResult]
    final_score: float | None
    critical_flag: bool
    created_at: datetime


class ConversationSummary(SQLModel):
    conversation_id: str
    channel: str
    language: str
    evaluated: bool
    status: str | None = None  # status of the latest evaluation
    final_score: float | None = None
    critical_flag: bool = False
    appeal_status: str | None = None  # latest appeal: draft | submitted | confirmed | revised
    transcript_length: int


# --- Appeals (operator disputes, reviewer answers) -------------------------


class AppealItem(SQLModel):
    criterion_id: str
    operator_comment: str = ""
    reviewer_comment: str = ""


class Appeal(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: str = Field(foreign_key="conversation.conversation_id", index=True)
    evaluation_id: int = Field(foreign_key="evaluation.id", index=True)  # the evaluation being appealed
    status: str = "draft"  # draft | submitted | confirmed | revised
    items: list[dict] = Field(sa_column=Column(JSON, nullable=False))
    revised_evaluation_id: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AppealWrite(SQLModel):
    evaluation_id: int
    items: list[AppealItem]


class AppealReviewWrite(SQLModel):
    items: list[AppealItem]  # only reviewer_comment is taken from these


class AppealRead(SQLModel):
    id: int
    conversation_id: str
    evaluation_id: int
    status: str
    items: list[AppealItem]
    revised_evaluation_id: int | None
    created_at: datetime
    updated_at: datetime
