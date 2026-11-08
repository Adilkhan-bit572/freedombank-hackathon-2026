"""results.json in the CQA hackathon format (schema 1.0)."""

from .service import EvaluationData

SCHEMA_VERSION = "1.0"
NOT_EVALUATED_ERROR = "Диалог не оценивался."
_MODES = {"ollama": "local", "gemini": "external_api"}


def result_entry(conversation_id: str, ev: EvaluationData | None) -> dict:
    if ev is None:
        return {"conversation_id": conversation_id, "status": "error", "criteria": [], "score": None,
                "error": NOT_EVALUATED_ERROR}
    if ev.status != "ok":
        return {"conversation_id": conversation_id, "status": "error", "criteria": [], "score": None,
                "error": ev.error or "Неизвестная ошибка."}
    return {
        "conversation_id": conversation_id,
        "status": "ok",
        "criteria": [
            {
                "criterion_id": c["criterion_id"],
                "value": c["value"],
                "rationale": c["rationale"],
                "evidence_turns": c["evidence_turns"],
            }
            for c in ev.criteria
        ],
        "score": {"final_score": ev.final_score, "critical_flag": ev.critical_flag},
    }


def model_info(evals: list[EvaluationData]) -> dict:
    used = [e for e in evals if e is not None and e.provider != "none" and e.model != "none"]
    modes = {_MODES.get(e.provider, "external_api") for e in used}
    names = sorted({e.model for e in used})
    return {
        "mode": modes.pop() if len(modes) == 1 else "hybrid" if modes else "local",
        "name": ", ".join(names) or "none",
    }


def build_results(team_name: str, items: list[tuple[str, EvaluationData | None]]) -> dict:
    """`items` = (conversation_id, evaluation or None), in output order."""
    return {
        "schema_version": SCHEMA_VERSION,
        "team_name": team_name,
        "model": model_info([ev for _, ev in items]),
        "results": [result_entry(cid, ev) for cid, ev in items],
    }


def validate_results(doc: dict, criteria: list[dict]) -> list[str]:
    """Check a results document against the format rules. Returns a list of problems."""
    problems: list[str] = []
    ids = [r.get("conversation_id") for r in doc.get("results", [])]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        problems.append(f"повторяющиеся conversation_id: {', '.join(map(str, dupes))}")
    expected = [c["id"] for c in criteria]
    defs = {c["id"]: c for c in criteria}
    for r in doc.get("results", []):
        cid = r.get("conversation_id")
        if r.get("status") == "error":
            if r.get("criteria") or r.get("score") is not None or not r.get("error"):
                problems.append(f"{cid}: ошибка должна иметь пустой criteria, score=null и текст error")
            continue
        got = [c.get("criterion_id") for c in r.get("criteria", [])]
        if sorted(got) != sorted(expected):
            problems.append(f"{cid}: критерии {got} вместо {expected}")
            continue
        for c in r["criteria"]:
            d, v = defs[c["criterion_id"]], c.get("value")
            if v is None:
                ok = d["nullable"]
            elif d["kind"] == "scale":
                ok = not isinstance(v, bool) and v in d["levels"]
            else:
                ok = isinstance(v, bool)
            if not ok:
                problems.append(f"{cid}: {c['criterion_id']} = {v!r} недопустимо")
            if not all(isinstance(t, int) and t >= 1 for t in c.get("evidence_turns", [])):
                problems.append(f"{cid}: {c['criterion_id']} — evidence_turns должны быть номерами с 1")
        s = r.get("score") or {}
        if s.get("critical_flag") is not next((c["value"] is True for c in r["criteria"]
                                               if defs[c["criterion_id"]]["kind"] == "critical"), False):
            problems.append(f"{cid}: critical_flag не совпадает с критерием critical")
        fs = s.get("final_score")
        if fs is not None and not (0 <= fs <= 100):
            problems.append(f"{cid}: final_score вне 0..100")
    return problems
