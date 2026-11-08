def compute_score(criteria: list[dict], results: list[dict]) -> tuple[float | None, bool]:
    """Return (final_score 0..100 rounded to 2 decimals, critical_flag).

    `criteria` is the checklist used for this evaluation. Criteria with value null (N/A)
    are excluded and their weight is redistributed proportionally; the top scale level
    gives the full weight. The critical flag is reported separately and does NOT change
    the score. The score is None when no weighted criterion is applicable.
    """
    by_id = {r["criterion_id"]: r for r in results}
    critical_flag = any(
        c["kind"] == "critical" and by_id.get(c["id"], {}).get("value") is True for c in criteria
    )

    earned = avail = 0.0
    for c in criteria:
        if c["kind"] == "critical" or not c["weight"]:
            continue
        value = by_id.get(c["id"], {}).get("value")
        if value is None:
            continue
        if c["kind"] == "bool":
            # a "negative" criterion describes a violation: "Да" (found) earns nothing
            frac = 1.0 if (value is True) != bool(c.get("negative")) else 0.0
        else:
            frac = value / c["max"]
        avail += c["weight"]
        earned += c["weight"] * frac

    if not avail:
        return None, critical_flag
    return round(earned / avail * 100, 2), critical_flag
