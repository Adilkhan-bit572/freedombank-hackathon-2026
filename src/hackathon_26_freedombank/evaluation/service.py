import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from ..llm import LLMClient, LLMError
from .criteria import enabled_criteria
from .prompts import build_system_prompt, build_user_prompt, language_reminder, speaker_role
from .scoring import compute_score

NO_OPERATOR_ERROR = "Живой оператор в диалоге не участвовал (отвечал только бот или клиент ушёл до соединения)."
EVIDENCE_KINDS = ("error", "missing", "good")

_TRUE = {"true", "yes", "да", "1"}
_FALSE = {"false", "no", "нет", "0"}
_NULL = {"", "null", "none", "n/a", "na", "н/д", "неприменимо"}


@dataclass
class EvaluationData:
    status: str  # "ok" | "error"
    criteria: list[dict] = field(default_factory=list)  # CriterionResult dicts, in checklist order
    final_score: float | None = None
    critical_flag: bool = False
    error: str | None = None
    provider: str = "none"
    model: str = "none"
    definitions: list[dict] | None = None  # criteria definitions used


def error_result(message: str, provider: str = "none", model: str = "none",
                 definitions: list[dict] | None = None) -> EvaluationData:
    return EvaluationData(status="error", error=message, provider=provider, model=model, definitions=definitions)


def _parse_json(text: str):
    m = re.search(r"[\[{][\s\S]*[\]}]", text)
    if not m:
        raise LLMError("LLM response is not JSON")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM returned invalid JSON: {e}") from e


_INVALID = object()


def _coerce(c: dict, value):
    """Convert an LLM value to the criterion's type. Returns None for N/A, _INVALID if unreadable."""
    if isinstance(value, str):
        s = value.strip().lower()
        if s in _NULL:
            return None
        if c["kind"] != "scale":
            return True if s in _TRUE else False if s in _FALSE else _INVALID
        try:
            value = float(s.replace(",", "."))
        except ValueError:
            return _INVALID
    if value is None:
        return None
    if c["kind"] == "scale":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
            return _INVALID
        return min(c["levels"], key=lambda lv: (abs(lv - value), lv))  # snap to the nearest level
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    return _INVALID


def _turns(raw, n_turns: int) -> list[int]:
    if not isinstance(raw, list):
        raw = [raw]
    out = set()
    for t in raw:
        if isinstance(t, bool):
            continue
        try:
            t = int(t)
        except (TypeError, ValueError):
            continue
        if 1 <= t <= n_turns:
            out.add(t)
    return sorted(out)


def _check(criteria: list[dict], parsed, n_turns: int) -> tuple[list[dict], list[str]]:
    """Normalise the LLM answer. Returns (CriterionResult dicts, problems)."""
    raw = parsed if isinstance(parsed, list) else parsed.get("criteria") if isinstance(parsed, dict) else None
    if not isinstance(raw, list):
        return [], ["в ответе нет списка criteria"]
    by_id: dict[str, dict] = {}
    for r in raw:
        if isinstance(r, dict):
            cid = str(r.get("criterion_id") or r.get("id") or "").strip()
            by_id.setdefault(cid, r)  # a duplicate answer keeps the first one

    results, problems = [], []
    for c in criteria:
        r = by_id.get(c["id"])
        if r is None:
            problems.append(f'нет критерия "{c["id"]}"')
            continue
        value = _coerce(c, r.get("value"))
        if value is _INVALID:
            problems.append(f'"{c["id"]}": недопустимое значение {r.get("value")!r}')
            continue
        if value is None and not c["nullable"]:
            problems.append(f'"{c["id"]}": null (N/A) не допускается')
            continue
        kind = r.get("evidence_kind")
        results.append({
            "criterion_id": c["id"],
            "title": c["title"],
            "kind": c["kind"],
            "negative": c.get("negative", False),
            "max": c.get("max"),
            "value": value,
            "rationale": str(r.get("rationale") or r.get("reason") or "").strip(),
            "evidence_turns": _turns(r.get("evidence_turns", []), n_turns),
            "evidence_kind": kind if kind in EVIDENCE_KINDS else None,
        })
    return results, problems


def response_schema(criteria: list[dict]) -> dict:
    """JSON schema of the expected answer: one object per criterion with only its allowed values.
    `rationale` comes before `value` so the model explains first and scores second."""

    def value_schema(c: dict) -> dict:
        allowed = list(c["levels"]) if c["kind"] == "scale" else [True, False]
        return {"enum": allowed + ([None] if c["nullable"] else [])}

    return {
        "type": "object",
        "properties": {
            "criteria": {
                "type": "array",
                "minItems": len(criteria),
                "maxItems": len(criteria),
                "items": {
                    "anyOf": [
                        {
                            "type": "object",
                            "properties": {
                                "criterion_id": {"const": c["id"]},
                                "rationale": {"type": "string"},
                                "evidence_kind": {"enum": [*EVIDENCE_KINDS, "none"]},
                                "evidence_turns": {"type": "array", "items": {"type": "integer"}},
                                "value": value_schema(c),
                            },
                            "required": ["criterion_id", "rationale", "evidence_kind", "evidence_turns", "value"],
                        }
                        for c in criteria
                    ]
                },
            }
        },
        "required": ["criteria"],
    }


def _ask(client: LLMClient, system: str, user: str, criteria: list[dict], n_turns: int):
    """Ask the LLM, validate, retry once with the problems. Returns (results, problems)."""
    schema = response_schema(criteria)
    problems: list[str] = []
    for attempt in range(2):
        prompt = user if not attempt else (
            user + "\n\nТвой предыдущий ответ был некорректен: " + "; ".join(problems)
            + ". Верни полный ответ заново в требуемом формате."
        )
        try:
            parsed = _parse_json(client.generate_json(system, prompt, schema))
        except LLMError as e:
            if "JSON" not in str(e):
                raise
            problems = [str(e)]
            continue
        results, problems = _check(criteria, parsed, n_turns)
        if not problems:
            return results, []
    return [], problems


def evaluate_conversation(
    transcript: list[dict],
    criteria: list[dict],
    general_rules: str,
    get_client: Callable[[], LLMClient],
    language: str | None = None,
) -> EvaluationData:
    """Evaluate one conversation with the enabled criteria of `criteria` (a normalised checklist).

    `language` is the record's language (RU/KZ/EN): rationales are written in it.
    Invalid answers are retried once with the list of problems; if the answer is still
    invalid, an error result is returned. LLMError (provider unreachable, rate limit, ...)
    propagates so the caller can retry or store it as an error.
    `get_client` is only called when the LLM is actually needed.
    """
    criteria = enabled_criteria(criteria)
    if not any(speaker_role(t.get("speaker")) == "operator" for t in transcript):
        return error_result(NO_OPERATOR_ERROR, definitions=criteria)

    client = get_client()
    system = build_system_prompt(criteria, general_rules, language)
    results, problems = _ask(client, system, build_user_prompt(transcript, language), criteria, len(transcript))
    if problems:
        return error_result("Ответ модели не прошёл проверку: " + "; ".join(problems),
                            client.provider, client.model, criteria)
    score, critical_flag = compute_score(criteria, results)
    return EvaluationData("ok", results, score, critical_flag, None, client.provider, client.model, criteria)


def revise_evaluation(
    transcript: list[dict],
    definitions: list[dict],
    previous: list[dict],
    appeal_items: list[dict],
    general_rules: str,
    get_client: Callable[[], LLMClient],
    language: str | None = None,
) -> EvaluationData:
    """Re-evaluate only the criteria the reviewer answered (non-empty reviewer_comment),
    taking the operator's appeal and the reviewer's comment into account. All other
    criteria keep their previous results; the score is recomputed over all of them."""
    answered = {i["criterion_id"]: i for i in appeal_items if (i.get("reviewer_comment") or "").strip()}
    targets = [c for c in definitions if c["id"] in answered]
    if not targets:
        raise ValueError("Нет критериев с комментарием проверяющего — пересматривать нечего.")
    prev = {r["criterion_id"]: r for r in previous}

    client = get_client()
    blocks = []
    for c in targets:
        p, item = prev.get(c["id"], {}), answered[c["id"]]
        blocks.append(
            f'criterion_id "{c["id"]}" — {c["title"]}\n'
            f'  Прежняя оценка: {json.dumps(p.get("value"), ensure_ascii=False)}; обоснование: {p.get("rationale", "")}\n'
            f'  Апелляция оператора: {item.get("operator_comment", "").strip() or "—"}\n'
            f'  Комментарий проверяющего: {item["reviewer_comment"].strip()}'
        )
    user = (
        build_user_prompt(transcript)
        + "\n\nПЕРЕСМОТР ОЦЕНКИ. Оператор оспорил оценки ниже, проверяющий ответил комментариями. "
        "Заново оцени только эти критерии по расшифровке, обязательно учитывая комментарий проверяющего "
        "(он имеет приоритет над прежней оценкой). Верни объекты только для этих критериев.\n\n"
        + "\n\n".join(blocks)
        + (f"\n\n{language_reminder(language)}" if language_reminder(language) else "")
    )
    system = build_system_prompt(targets, general_rules, language)
    results, problems = _ask(client, system, user, targets, len(transcript))
    if problems:
        raise LLMError("Ответ модели при пересмотре не прошёл проверку: " + "; ".join(problems))

    new = {r["criterion_id"]: {**r, "revised": True} for r in results}
    merged = [new.get(c["id"]) or prev[c["id"]] for c in definitions if c["id"] in new or c["id"] in prev]
    score, critical_flag = compute_score(definitions, merged)
    return EvaluationData("ok", merged, score, critical_flag, None, client.provider, client.model, definitions)
