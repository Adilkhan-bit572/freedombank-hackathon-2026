"""Default checklist: "Чек-лист качества чатов" (CQA hackathon), results format JSON 1.0.

The active checklist lives in the database (table `checklist`) and can be edited from
the UI / `PUT /checklist`. This module holds the factory default and the validation
rules shared by the API and the evaluator.

Criterion fields:
  id          - criterion_id in results.json (lowercase latin, digits, "_")
  title       - shown in the UI
  kind        - "bool" (true/false), "scale" (one of `levels`) or "critical"
                (true = gross violation; no weight, does not change the score)
  nullable    - whether null (N/A) is allowed
  levels      - allowed values for "scale", ascending; the top level gives the full weight
  weight      - points before N/A redistribution (0..MAX_WEIGHT)
  description - what "Да" / N/A mean (goes into the LLM prompt)
  level_descriptions - {"20": "...", ...} for "scale" (goes into the LLM prompt)
  negative    - "bool" only: the criterion describes a violation, so true = 0 points (shown red)
  visible     - listed in the main "+" panel (Settings checkbox)
  enabled     - used for evaluations ("+" pressed)
  comment     - reviewer's note to the AI for this criterion (goes into the LLM prompt)
"""

import re

KINDS = ("bool", "scale", "critical")
MAX_WEIGHT = 50
# The hackathon results format requires exactly these criteria.
STANDARD_IDS = ("contact", "discovery", "identification", "consultation", "empathy", "dialogue", "closure", "critical")
_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")

DEFAULT_GENERAL_RULES = """\
«Нет» — действие было нужно, но оператор его пропустил или выполнил неправильно. N/A (null) — критерий неприменим по условию; N/A ставится только там, где он разрешён.
Общий вопрос о тарифах не требует идентификации. Если требовалась проверка личности перед защищённым действием и она не подтверждена в чате, ставь «Нет».
Консультация оценивает, правильно и полно ли решён запрос. Ведение диалога оценивает, насколько понятно и последовательно оператор общался. Ясный ответ на один из двух важных вопросов может получить высокий балл за ведение диалога и частичный за консультацию.
Предложение услуги в обход компании: оператор предлагает перевести деньги ему лично для инвестирования или просит личный номер клиента, чтобы оказать платную консультацию в частном порядке. Достаточно самого предложения; согласие клиента или перевод денег не требуются.
Порог первой реакции в 3 минуты, теги и вложения в оценку не входят.
Обоснование: укажи конкретную реплику или системное сообщение и коротко поясни, что оно подтверждает. Для пропущенного действия укажи реплику, где оно ожидалось. Для N/A объясни, какое условие неприменимости выполнено. Пример: «Завершение — Нет. После ответа на вопрос оператор закрыл чат без прощания. Основание — последняя реплика оператора и сообщение о закрытии чата».
Один и тот же чек-лист применяется к чатам на русском, казахском и английском."""

DEFAULT_CRITERIA: list[dict] = [
    {
        "id": "contact", "title": "Установление контакта", "kind": "bool", "nullable": False, "weight": 10,
        "description": "Да — оператор поздоровался на языке клиента и представился в первом ответе.",
    },
    {
        "id": "discovery", "title": "Выявление потребности", "kind": "bool", "nullable": True, "weight": 15,
        "description": "Да — оператор учёл известные детали и уточнил недостающее до ответа. "
                       "N/A — данных для ответа хватало с самого начала.",
    },
    {
        "id": "identification", "title": "Идентификация", "kind": "bool", "nullable": True, "weight": 20,
        "description": "Да — проверка личности подтверждена до раскрытия данных или защищённого действия. "
                       "N/A — запрос не требовал идентификации.",
    },
    {
        "id": "consultation", "title": "Корректная и полная консультация", "kind": "scale", "nullable": True,
        "levels": [0, 5, 10, 15, 20], "weight": 20,
        "description": "Оцени ответ или следующий шаг по шкале. "
                       "N/A — чат закончился до того, как клиент сформулировал запрос.",
        "level_descriptions": {
            "20": "Все существенные вопросы закрыты или дан корректный следующий шаг.",
            "15": "Основной вопрос решён, пропущена второстепенная деталь.",
            "10": "Часть запроса закрыта, существенный вопрос остался открытым.",
            "5": "Есть общая подсказка, но клиенту всё ещё непонятно, как действовать.",
            "0": "Ответа по существу нет или ключевая рекомендация ошибочна.",
        },
    },
    {
        "id": "empathy", "title": "Эмпатия и клиентоориентированность", "kind": "bool", "nullable": False,
        "weight": 15,
        "description": "Да — оператор вежлив и, если клиент выразил недовольство или описал неудобство, "
                       "отреагировал на конкретную проблему.",
    },
    {
        "id": "dialogue", "title": "Управление диалогом, скорость и грамотность", "kind": "scale",
        "nullable": False, "levels": [0, 4, 7, 10], "weight": 15,
        "description": "Оцени ясность, порядок ответов и предупреждение об ожидании по шкале.",
        "level_descriptions": {
            "10": "Ответы ясные и связные. Если было явное ожидание, оператор предупредил.",
            "7": "Один заметный сбой, но клиент может понять ответ и продолжить.",
            "4": "Клиенту приходится переспрашивать из-за формулировок или порядка ответов.",
            "0": "Из-за бессвязных или противоречивых реплик ход диалога непонятен.",
        },
    },
    {
        "id": "closure", "title": "Завершение", "kind": "bool", "nullable": True, "weight": 5,
        "description": "Да — оператор подвёл итог или предложил дальнейшую помощь и попрощался. "
                       "N/A — чат оборвался до возможности его завершить.",
    },
    {
        "id": "critical", "title": "Грубые ошибки", "kind": "critical", "nullable": False, "weight": 0,
        "description": "Да (true) — выявлено оскорбление клиента, предложение платной услуги в обход компании "
                       "или раскрытие конфиденциальной информации. Нет (false) — ни одно из трёх не выявлено.",
    },
    {
        # Extra criterion (not part of the hackathon 8): off by default, switched on with "+".
        "id": "pushback", "title": "Отталкивание", "kind": "bool", "negative": True, "nullable": True,
        "weight": 10, "enabled": False,
        "description": "Нарушение: Да (true) — выявлено отталкивание: оператор долго брал диалог после переадресации "
                       "от ИИ-ассистента (дольше порога первой реакции в 3 минуты по таймкодам), а затем в ответах "
                       "прослеживалась скрытая агрессия по интонации и манере ведения диалога (сухость, "
                       "пренебрежение, раздражение, желание поскорее отделаться от клиента). Нет (false) — "
                       "отталкивания нет. N/A — переадресации от ИИ-ассистента к оператору не было.",
    },
]


class ChecklistError(ValueError):
    """The checklist definition is invalid."""


def normalise_criteria(criteria: list[dict]) -> list[dict]:
    """Validate a checklist and return it in canonical form. Raises ChecklistError."""
    if not isinstance(criteria, list) or not criteria:
        raise ChecklistError("Нужен хотя бы один критерий.")
    out, seen = [], set()
    for n, c in enumerate(criteria, 1):
        if not isinstance(c, dict):
            raise ChecklistError(f"Критерий №{n}: ожидается объект.")
        cid = str(c.get("id") or "").strip()
        if not _ID_RE.match(cid):
            raise ChecklistError(f"Критерий №{n}: код «{cid}» — только строчная латиница, цифры и «_», с буквы.")
        if cid in seen:
            raise ChecklistError(f"Код «{cid}» повторяется.")
        seen.add(cid)
        title = str(c.get("title") or "").strip()
        if not title:
            raise ChecklistError(f"«{cid}»: нужно название.")
        kind = c.get("kind")
        if kind not in KINDS:
            raise ChecklistError(f"«{cid}»: тип должен быть одним из {', '.join(KINDS)}.")
        item = {
            "id": cid,
            "title": title,
            "kind": kind,
            "nullable": bool(c.get("nullable")) and kind != "critical",
            "negative": bool(c.get("negative")) and kind == "bool",
            "weight": 0,
            "description": str(c.get("description") or "").strip(),
            # missing in checklists saved before these fields existed -> visible and evaluated
            "visible": c.get("visible") is not False,
            "enabled": c.get("enabled") is not False,
            "comment": str(c.get("comment") or "").strip()[:1000],
        }
        if kind != "critical":
            try:
                weight = float(c.get("weight"))
            except (TypeError, ValueError):
                raise ChecklistError(f"«{cid}»: вес должен быть числом.") from None
            if not 0 <= weight <= MAX_WEIGHT:
                raise ChecklistError(f"«{cid}»: вес должен быть от 0 до {MAX_WEIGHT}.")
            item["weight"] = int(weight) if weight == int(weight) else weight
        if kind == "scale":
            try:
                levels = sorted({int(v) for v in c.get("levels") or []})
            except (TypeError, ValueError):
                raise ChecklistError(f"«{cid}»: ступени шкалы должны быть целыми числами.") from None
            if len(levels) < 2 or levels[0] < 0 or levels[-1] <= 0:
                raise ChecklistError(f"«{cid}»: нужно минимум две ступени ≥ 0, верхняя > 0.")
            item["levels"] = levels
            item["max"] = levels[-1]
            descs = c.get("level_descriptions") or {}
            item["level_descriptions"] = {
                str(lv): str(descs.get(str(lv)) or descs.get(lv) or "").strip() for lv in reversed(levels)
            }
        out.append(item)
    if sum(1 for c in out if c["kind"] == "critical") > 1:
        raise ChecklistError("Критерий типа critical может быть только один.")
    if not any(c["kind"] != "critical" and c["weight"] > 0 and c["enabled"] for c in out):
        raise ChecklistError("Нужен хотя бы один включённый критерий с весом больше 0.")
    return out


def enabled_criteria(criteria: list[dict]) -> list[dict]:
    """The criteria an evaluation uses: the ones switched on with "+"."""
    return [c for c in criteria if c.get("enabled", True)]
