from __future__ import annotations

import re

DATE_PATTERNS = [
    re.compile(r"\[(\d{4})-(\d{2})-(\d{2})\]"),
    re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日"),
    re.compile(r"^(\d{2})-(\d{2})\s", re.MULTILINE),
]


def extract_date(text: str) -> str | None:
    for pattern in DATE_PATTERNS:
        m = pattern.search(text[:200])
        if m:
            groups = m.groups()
            if len(groups) == 3 and len(groups[0]) == 4:
                _, month, day = groups
            else:
                month, day = groups[0], groups[1]
            return f"{int(month):02d}-{int(day):02d}"
    return None
