"""Outreach pipeline: one CSV row per company, moved through fixed stages.

The point is to measure the funnel (contacted -> replied -> interview), not to collect PR counts.
"""
from __future__ import annotations

import csv
import os
from datetime import date

STAGES = ["found", "pr_open", "pr_merged", "contacted", "replied", "call", "trial", "offer",
          "rejected", "dropped"]
FIELDS = ["company", "stage", "role", "channel", "updated", "note"]


def load(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def save(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def track(path: str, company: str, stage: str, role: str = "", channel: str = "", note: str = "") -> dict:
    if stage not in STAGES:
        raise ValueError(f"stage must be one of: {', '.join(STAGES)}")
    rows = load(path)
    row = next((r for r in rows if r["company"].lower() == company.lower()), None)
    if row is None:
        row = {k: "" for k in FIELDS}
        row["company"] = company
        rows.append(row)
    row["stage"] = stage
    row["updated"] = str(date.today())
    for k, v in (("role", role), ("channel", channel), ("note", note)):
        if v:
            row[k] = v
    save(path, rows)
    return row


def funnel(path: str) -> str:
    rows = load(path)
    if not rows:
        return "Pipeline is empty. Add a company: python3 -m radar track \"Company\" contacted"
    counts = {s: sum(r["stage"] == s for r in rows) for s in STAGES}
    reached = lambda s: sum(STAGES.index(r["stage"]) >= STAGES.index(s)
                            for r in rows if r["stage"] in STAGES[:8])
    lines = [f"{s:<10} {counts[s]}" for s in STAGES if counts[s]]
    contacted, replied, call = reached("contacted"), reached("replied"), reached("call")
    lines.append("")
    lines.append(f"reply rate: {replied}/{contacted}" + (f" = {replied / contacted:.0%}" if contacted else ""))
    lines.append(f"call rate:  {call}/{contacted}" + (f" = {call / contacted:.0%}" if contacted else ""))
    return "\n".join(lines)
