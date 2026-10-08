import re
import unicodedata


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def duplicate_key(title: str, authors: list[str], year: int) -> tuple:
    return (normalize(title), tuple(sorted(normalize(a) for a in authors)), int(year))


def is_strong_duplicate(a: tuple, b: tuple) -> bool:
    """Same normalized title + same author set + same year (PRD s11)."""
    return a == b
