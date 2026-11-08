"""Evaluate a set of dialogues and write results.json in the hackathon format (schema 1.0).

Works without the API server. Uses the active checklist from the database (the one edited
in the UI), or the default checklist with --default-checklist.

    uv run python scripts/export_results.py --input src/hackathon_26_freedombank/data.json --out results/dev/results.json
    uv run python scripts/export_results.py --input prod.json --out results/prod/results.json --provider gemini

The input is the data.json format ({"data": {"records": [...]}}), a {"records": [...]} object
or a plain list of records. Progress is saved after every dialogue; re-running with
--resume skips the ones already evaluated successfully in the output file.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from sqlmodel import Session

from hackathon_26_freedombank import config
from hackathon_26_freedombank.db import engine, init_db
from hackathon_26_freedombank.evaluation.results import build_results, validate_results
from hackathon_26_freedombank.evaluation.service import EvaluationData, error_result, evaluate_conversation
from hackathon_26_freedombank.evaluation.store import active_checklist, default_checklist
from hackathon_26_freedombank.llm import LLMError, get_llm_client


def load_records(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("data", data).get("records") if isinstance(data, dict) else data
    if not isinstance(records, list) or not records:
        sys.exit(f"{path}: no records found")
    ids = [r.get("conversation_id") for r in records]
    if len(set(ids)) != len(ids) or not all(ids):
        sys.exit(f"{path}: conversation_id values are missing or not unique")
    return records


def load_previous(path: Path) -> dict[str, EvaluationData]:
    """ok entries from an earlier run (for --resume)."""
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    mode_name = doc.get("model", {}).get("name", "unknown")
    provider = "ollama" if doc.get("model", {}).get("mode") == "local" else "gemini"
    out = {}
    for r in doc.get("results", []):
        if r.get("status") == "ok":
            out[r["conversation_id"]] = EvaluationData(
                status="ok",
                criteria=r["criteria"],
                final_score=r["score"]["final_score"],
                critical_flag=r["score"]["critical_flag"],
                provider=provider,
                model=mode_name,
            )
    return out


def evaluate_with_retry(record, criteria, rules, client_factory, retries: int, wait: float) -> EvaluationData:
    for attempt in range(retries + 1):
        try:
            return evaluate_conversation(record.get("transcript") or [], criteria, rules, client_factory)
        except LLMError as e:
            if e.retryable and attempt < retries:
                print(f"    rate limited, waiting {wait:.0f}s ({attempt + 1}/{retries})", flush=True)
                time.sleep(wait)
                continue
            return error_result(f"Не удалось получить ответ модели: {e}")
        except Exception as e:  # never lose a dialogue from the file
            return error_result(f"Ошибка обработки: {type(e).__name__}: {e}")
    raise AssertionError("unreachable")


def write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--provider", choices=["gemini", "ollama"], help="default: LLM_PROVIDER from .env")
    p.add_argument("--team", default=config.TEAM_NAME)
    p.add_argument("--pause", type=float, default=3.0, help="seconds between LLM calls")
    p.add_argument("--retries", type=int, default=3, help="retries on rate limits")
    p.add_argument("--retry-wait", type=float, default=40.0)
    p.add_argument("--resume", action="store_true", help="keep ok results already in --out")
    p.add_argument("--default-checklist", action="store_true", help="ignore the edited checklist in the DB")
    p.add_argument("--limit", type=int, help="only the first N records (for a quick test)")
    args = p.parse_args()

    records = load_records(args.input)[: args.limit]
    if args.default_checklist:
        criteria, rules = default_checklist()
    else:
        init_db()
        with Session(engine) as s:
            checklist = active_checklist(s)
            criteria, rules = checklist.criteria, checklist.general_rules

    client = None

    def client_factory():
        nonlocal client
        client = client or get_llm_client(args.provider)
        return client

    done = load_previous(args.out) if args.resume else {}
    items: list[tuple[str, EvaluationData]] = []
    for n, rec in enumerate(records, 1):
        cid = rec["conversation_id"]
        if cid in done:
            items.append((cid, done[cid]))
            print(f"[{n}/{len(records)}] {cid}: kept from previous run")
            continue
        t0 = time.monotonic()
        ev = evaluate_with_retry(rec, criteria, rules, client_factory, args.retries, args.retry_wait)
        items.append((cid, ev))
        msg = f"score {ev.final_score}{' CRITICAL' if ev.critical_flag else ''}" if ev.status == "ok" else f"ERROR {ev.error}"
        print(f"[{n}/{len(records)}] {cid}: {msg} ({time.monotonic() - t0:.1f}s)", flush=True)
        write(args.out, build_results(args.team, items))  # save progress
        if n < len(records) and ev.provider != "none":
            time.sleep(args.pause)

    doc = build_results(args.team, items)
    write(args.out, doc)
    problems = validate_results(doc, criteria)
    ok = sum(1 for _, ev in items if ev.status == "ok")
    print(f"\n{args.out}: {len(items)} dialogues, {ok} ok, {len(items) - ok} error; model {doc['model']}")
    if problems:
        print("Validation problems:\n  " + "\n  ".join(problems))
        sys.exit(1)
    print("Validation passed.")


if __name__ == "__main__":
    main()
