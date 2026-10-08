"""Embedding-index text, vector serialisation, cosine ranking, recommendations.
The model encoder is injected (Sentence-Transformers in production), so ranking logic is testable."""
import hashlib
import re
from dataclasses import dataclass
import numpy as np

DEFAULT_THRESHOLD = 0.35
MAX_QUERY_LEN = 500


def build_index_text(title: str, abstract: str, keywords: list[str]) -> str:
    """Identical composition for documents and queries' counterpart (PRD s18)."""
    return f"Title: {title.strip()}\n\nAbstract: {abstract.strip()}\n\nKeywords: {', '.join(k.strip() for k in keywords)}"


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_query(q: str) -> str:
    q = re.sub(r"\s+", " ", q or "").strip()
    return q[:MAX_QUERY_LEN]


def to_blob(vec) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def cosine_scores(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return np.zeros(0, dtype=np.float32)
    q = query / (np.linalg.norm(query) or 1.0)
    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0] = 1.0
    return (matrix / norms[:, None]) @ q


@dataclass
class Candidate:
    work_id: int
    vector: np.ndarray
    year: int = 0
    program_id: int | None = None
    department_id: int | None = None
    category_id: int | None = None
    keywords: frozenset = frozenset()


def rank(query_vec, candidates: list[Candidate], threshold=DEFAULT_THRESHOLD, limit=20):
    """`candidates` MUST already be access- and filter-restricted by the caller."""
    if not candidates:
        return []
    scores = cosine_scores(np.asarray(query_vec, dtype=np.float32),
                           np.vstack([c.vector for c in candidates]))
    hits = [(c.work_id, float(s)) for c, s in zip(candidates, scores) if s >= threshold]
    return sorted(hits, key=lambda t: -t[1])[:limit]


def recommend(target: Candidate, candidates: list[Candidate],
              threshold=DEFAULT_THRESHOLD, count=5):
    """Semantic similarity primary; metadata overlap is a small secondary boost."""
    pool = [c for c in candidates if c.work_id != target.work_id]
    if not pool:
        return []
    sims = cosine_scores(target.vector, np.vstack([c.vector for c in pool]))
    out = []
    for c, s in zip(pool, sims):
        if s < threshold:
            continue
        overlap = 0.0
        overlap += 0.02 if c.program_id and c.program_id == target.program_id else 0
        overlap += 0.01 if c.department_id and c.department_id == target.department_id else 0
        overlap += 0.02 if c.category_id and c.category_id == target.category_id else 0
        if c.keywords and target.keywords:
            overlap += 0.03 * len(c.keywords & target.keywords) / len(c.keywords | target.keywords)
        overlap += 0.01 if abs(c.year - target.year) <= 2 else 0
        out.append((c.work_id, float(s), float(s) + overlap))
    out.sort(key=lambda t: -t[2])
    return [(w, s) for w, s, _ in out[:count]]


def percent(score: float) -> str:
    return f"Semantic relevance: {max(0, round(score * 100))}%"
