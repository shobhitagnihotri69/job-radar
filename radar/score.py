"""Keyword scoring of a company against your domain (weights live in config.json)."""
from __future__ import annotations

import re


def score(row: dict, keywords: dict[str, int]) -> tuple[int, list[str]]:
    text = " ".join([row.get("one_liner", ""), row.get("description", ""),
                     row.get("industries", "")]).lower()
    hits = [k for k in keywords if re.search(k, text)]
    return sum(keywords[k] for k in hits), hits


def key(row: dict) -> str:
    return f'{row["source"]}|{row["name"].strip().lower()}'
