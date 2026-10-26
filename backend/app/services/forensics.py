"""Explainable PDF tamper indicators for FDR review."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pikepdf


def _metadata_value(metadata: Any, key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    return str(value).strip()


def _dates_match(created: str, modified: str) -> bool:
    def parse(value: str) -> datetime | None:
        pdf_date = re.fullmatch(
            r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?(?:Z|([+-])(\d{2})'?((?:\d{2})?)'?)?",
            value,
        )
        if pdf_date:
            parts = [int(part) if part else 0 for part in pdf_date.groups()[:6]]
            return datetime(*[parts[0], parts[1] or 1, parts[2] or 1, *parts[3:]])
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    created_date = parse(created)
    modified_date = parse(modified)
    if created_date is None or modified_date is None:
        return created == modified
    return created_date == modified_date


def inspect_pdf(pdf_path: str | Path) -> dict[str, Any]:
    """Check revision markers and PDF creation/modification metadata."""
    path = Path(pdf_path)
    data = path.read_bytes()
    eof_count = data.count(b"%%EOF")

    with pikepdf.open(path) as document:
        metadata = document.docinfo
        created = _metadata_value(metadata, "/CreationDate")
        modified = _metadata_value(metadata, "/ModDate")

    dates_match = _dates_match(created, modified) if created and modified else None
    flags: list[str] = []
    if eof_count > 1:
        flags.append("multiple_eof_markers")
    if dates_match is False:
        flags.append("creation_modified_date_mismatch")

    return {
        "source_file": path.name,
        "is_valid_pdf": True,
        "eof_count": eof_count,
        "incremental_revisions": max(0, eof_count - 1),
        "creation_date": created,
        "modified_date": modified,
        "creation_modified_match": dates_match,
        "flags": flags,
    }