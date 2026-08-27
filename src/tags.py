import re

from typing import Optional

TAG_TOKEN_RE = re.compile(r"#(\S+)")


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


def extract_tag_filter(text: str) -> tuple[Optional[str], str]:
    """Pull the first '#tag' token out of free text for exact-match filtering.

    Returns (tag, remaining_text) — tag is None if no '#' token is present.
    Case-sensitive, no normalization: matches tags exactly as stored (see normalize_tag).
    """
    match = TAG_TOKEN_RE.search(text)
    if not match:
        return None, text
    remaining = re.sub(r"\s+", " ", text[:match.start()] + text[match.end():]).strip()
    return match.group(1), remaining
