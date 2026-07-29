import re


def normalize_tag(raw: str) -> str:
    """Strip a leading '#' and surrounding whitespace, collapse internal whitespace to '-'."""
    tag = raw.strip().lstrip("#").strip()
    return re.sub(r"\s+", "-", tag)


def normalize_tags(raw_tags: list[str]) -> list[str]:
    """Normalize a list of raw tag inputs for one note: drop empties, dedupe exact repeats, preserve order."""
    seen: list[str] = []
    for raw in raw_tags:
        tag = normalize_tag(raw)
        if tag and tag not in seen:
            seen.append(tag)
    return seen
