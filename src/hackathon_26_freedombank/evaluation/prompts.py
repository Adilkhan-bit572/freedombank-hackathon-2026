"""Prompts for the evaluation LLM, built from the active checklist."""

import json
import re
from datetime import datetime

_INTRO = """Ты — строгий и справедливый эксперт по контролю качества чатов и звонков контакт-центра Freedom Broker. Оцениваешь ТОЛЬКО работу живого оператора, а не клиента. В диалоге могут быть реплики бота (AI-ассистента) и системные сообщения: их не оценивай, но используй как контекст и как подтверждение (например, сообщение о закрытии чата или о переводе на оператора). Приветствие бота не засчитывается оператору. Не выдумывай реплики, опирайся только на расшифровку. Время у реплик — от начала диалога (мм:сс)."""

# Record language -> language of the rationales (the operator reads them).
_LANGUAGES = {
    "RU": "на русском языке",
    "KZ": "на казахском языке (қазақ тілінде)",
    "KK": "на казахском языке (қазақ тілінде)",
    "EN": "на английском языке (in English)",
}


# The same requirement written in the target language: models follow it far more reliably
# than an instruction inside a Russian prompt.
_LANGUAGE_REMINDERS = {
    "RU": 'Пиши каждое поле "rationale" на русском языке.',
    "KZ": 'Әрбір "rationale" өрісін қазақ тілінде жаз (орыс тілінде емес).',
    "KK": 'Әрбір "rationale" өрісін қазақ тілінде жаз (орыс тілінде емес).',
    "EN": 'Write every "rationale" field in English (not in Russian).',
}


def language_reminder(language: str | None) -> str:
    return _LANGUAGE_REMINDERS.get((language or "").upper(), "")


def _value_spec(c: dict) -> str:
    if c["kind"] == "scale":
        spec = "одно из чисел " + ", ".join(str(v) for v in c["levels"])
    elif c["kind"] == "critical":
        spec = 'true («Да» = грубая ошибка) / false («Нет»)'
    elif c.get("negative"):
        spec = 'true («Да» = нарушение выявлено) / false («Нет» = нарушения нет)'
    else:
        spec = "true («Да») / false («Нет»)"
    return spec + (" / null (N/A)" if c["nullable"] else "; null запрещён")


def _criterion_block(n: int, c: dict) -> str:
    weight = "без баллов" if c["kind"] == "critical" else f"вес {c['weight']}"
    lines = [f'{n}. criterion_id "{c["id"]}" — {c["title"]} ({_value_spec(c)}; {weight}).']
    if c.get("description"):
        lines.append(f"   {c['description']}")
    for level, text in (c.get("level_descriptions") or {}).items():
        if text:
            lines.append(f"   {level} — {text}")
    if c.get("comment"):
        lines.append(f"   Указание проверяющего (обязательно учти): {c['comment']}")
    return "\n".join(lines)


def build_system_prompt(criteria: list[dict], general_rules: str, language: str | None = None) -> str:
    ids = [c["id"] for c in criteria]
    example = {
        "criteria": [
            {"criterion_id": ids[0], "rationale": "…", "evidence_kind": "error", "evidence_turns": [1], "value": "…"},
        ]
    }
    lang = _LANGUAGES.get((language or "").upper(), "на языке диалога")
    return "\n\n".join(
        part
        for part in [
            _INTRO,
            "Критерии:\n" + "\n".join(_criterion_block(n, c) for n, c in enumerate(criteria, 1)),
            "Правила:\n" + general_rules.strip() if general_rules.strip() else "",
            f"""Реплики пронумерованы с 1 по исходному транскрипту (включая клиента, бота и системные сообщения): [#N мм:сс Роль].
Для каждого критерия верни объект {{"criterion_id": код, "rationale": обоснование, "evidence_kind": вид основания, "evidence_turns": [номера реплик], "value": значение}}:
- rationale — 1–2 коротких предложения {lang}, обращаясь к оператору простыми словами: что было сделано не так и как надо было (или что сделано хорошо). Пиши rationale {lang}, даже если инструкции на русском.
- evidence_kind — "error": реплика, где оператор ошибся; "missing": нужного действия не было, evidence_turns — реплика, после которой оно должно было прозвучать; "good": удачный пример; "none": для N/A или когда сослаться не на что.
- evidence_turns — номера подтверждающих реплик.
- value — оценка, согласованная с обоснованием. Сначала обоснуй, затем оцени.
Верни ровно {len(ids)} объектов, каждый criterion_id ровно один раз: {", ".join(ids)}.
Ответ — только JSON такого вида: {json.dumps(example, ensure_ascii=False)}""",
        ]
        if part
    )


def speaker_role(speaker: str | None) -> str:
    """Map a raw `speaker` value from the data to operator / caller / bot / system."""
    sp = (speaker or "").lower()
    if sp == "system":
        return "system"
    if re.search(r"client|customer|user|caller|клиент|абонент|звонящ", sp):
        return "caller"
    if re.search(r"^(bot|assistant|ai|aim|virtual)|бот|ассистент", sp):
        return "bot"
    return "operator"


ROLE_SHORT = {"operator": "Оператор", "caller": "Клиент", "bot": "Бот", "system": "Система"}


def _seconds(ts) -> float | None:
    """Timestamp -> seconds: "mm:ss" / "hh:mm:ss" are offsets; ISO datetimes are absolute (epoch)."""
    if ts is None or ts == "":
        return None
    if isinstance(ts, (int, float)):
        return float(ts)
    s = str(ts).strip()
    if re.fullmatch(r"\d+(:\d+){1,2}(\.\d+)?", s):
        total = 0.0
        for part in s.split(":"):
            total = total * 60 + float(part)
        return total
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def relative_times(transcript: list[dict]) -> list[str]:
    """"mm:ss" from the start of the dialogue for each turn ("" when unknown). Voice calls carry ISO
    datetimes; showing offsets keeps the prompt short and makes the 3-minute rule measurable."""
    secs = [_seconds(t.get("timestamp")) for t in transcript]
    start = next((s for s in secs if s is not None), None)
    out = []
    for s in secs:
        if s is None or start is None:
            out.append("")
            continue
        d = max(0, int(s - start))
        out.append(f"{d // 3600}:{d // 60 % 60:02d}:{d % 60:02d}" if d >= 3600 else f"{d // 60:02d}:{d % 60:02d}")
    return out


def build_user_prompt(transcript: list[dict], language: str | None = None) -> str:
    # 1-based numbering over the raw stored transcript: evidence_turns must match the
    # original array (results format), and the frontend shows the same numbers.
    times = relative_times(transcript)
    lines = [
        f"[#{i}{' ' + times[i - 1] if times[i - 1] else ''} {ROLE_SHORT[speaker_role(t.get('speaker'))]}] {t.get('text', '')}"
        for i, t in enumerate(transcript, 1)
    ]
    reminder = language_reminder(language)
    return "Расшифровка диалога:\n\n" + "\n".join(lines) + (f"\n\n{reminder}" if reminder else "")
