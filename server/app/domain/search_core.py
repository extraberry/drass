"""Embedding-index text, vector serialisation, cosine ranking, recommendations.
The model encoder is injected (Sentence-Transformers in production), so ranking logic is testable."""
import difflib
import hashlib
import re
from dataclasses import dataclass
import numpy as np

DEFAULT_THRESHOLD = 0.25
LEXICAL_MIN = 0.5        # a result with at least this word-match score is shown even if its meaning-score is low
INDEX_SCHEME = "v2"      # bump when the way documents are embedded changes (marks old vectors stale)
MAX_QUERY_LEN = 500


def build_index_text(title: str, abstract: str, keywords: list[str]) -> str:
    """Identical composition for documents and queries' counterpart (PRD s18)."""
    return f"Title: {title.strip()}\n\nAbstract: {abstract.strip()}\n\nKeywords: {', '.join(k.strip() for k in keywords)}"


MAX_PIECES = 14


def build_index_pieces(title: str, abstract: str, keywords: list[str]) -> list[str]:
    """Several short texts per work, embedded separately. A single long text is cut off by the model (about 256 word
    pieces), so keywords and the end of the abstract were never 'seen'. Pieces: 0 = full text (as before),
    1 = title + keywords, then overlapping 2-sentence windows of the abstract."""
    title, abstract = (title or "").strip(), (abstract or "").strip()
    kws = ", ".join(k.strip() for k in keywords if k and k.strip())
    pieces = [build_index_text(title, abstract, keywords), f"{title}. {kws}".strip(". ")]
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", abstract) if x.strip()]
    if len(sentences) <= 2:
        windows = sentences
    else:
        windows = [" ".join(sentences[i:i + 2]) for i in range(len(sentences) - 1)]
    pieces += windows[: MAX_PIECES - len(pieces)]
    return [p for p in pieces if p]


def text_hash(text: str) -> str:
    return hashlib.sha256((INDEX_SCHEME + "\n" + text).encode("utf-8")).hexdigest()


def normalize_query(q: str) -> str:
    q = re.sub(r"\s+", " ", q or "").strip()
    return q[:MAX_QUERY_LEN]


def to_blob(vec) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def matrix_from_blob(blob: bytes, dim: int | None) -> np.ndarray:
    """One row per embedded piece. Old single-vector blobs load as a 1-row matrix."""
    flat = from_blob(blob)
    if dim and dim > 0 and flat.size % dim == 0:
        return flat.reshape(-1, dim)
    return flat.reshape(1, -1)


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
    title: str = ""
    abstract: str = ""


def _primary(c: Candidate) -> np.ndarray:
    return np.atleast_2d(c.vector)[0]


def dense_score(query_vec, c: Candidate) -> float:
    """Best cosine similarity between the query and any embedded piece of the work."""
    m = np.atleast_2d(np.asarray(c.vector, dtype=np.float32))
    return float(cosine_scores(np.asarray(query_vec, dtype=np.float32), m).max())


# ---- word matching (catches exact words, names, acronyms and small typos that the meaning-model misses) ----
_STOP = frozenset("a an the of to in on for and or with by is are be was were that this it as at from using use based into "
                  "about how what which who whom do does can i my me we our you your".split())


def _stem(t: str) -> str:
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    for suf in ("ization", "ations", "ation", "ments", "ment", "ness", "ings", "ing", "ers", "er", "ed", "ly"):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            return t[: -len(suf)]
    if len(t) > 4 and t.endswith("es") and (t[-3] in "sxz" or t.endswith(("ches", "shes"))):
        return t[:-2]                                        # classes -> class, boxes -> box
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]                                        # badges -> badge, students -> student
    return t


def stems(text: str, drop_stop: bool = True) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [_stem(t) for t in toks if not (drop_stop and t in _STOP)]


def _term_in_field(term: str, vocab: set[str]) -> float:
    """1.0 exact, 0.85 one is the start of the other (e.g. 'monitor' / 'monitoring'), 0.75 close spelling, else 0."""
    if term in vocab:
        return 1.0
    if len(term) >= 4:
        for w in vocab:
            if len(w) >= 4 and (w.startswith(term) or term.startswith(w)):
                return 0.85
    if len(term) >= 5:
        if difflib.get_close_matches(term, vocab, n=1, cutoff=0.84):
            return 0.75
    return 0.0


def _acronyms(*texts: str) -> set[str]:
    """Initials of every run of 2-5 consecutive words ('Learning Management System' -> 'lms')."""
    out = set()
    for text in texts:
        words = [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _STOP]
        for i in range(len(words)):
            for n in range(2, 6):
                if i + n <= len(words):
                    out.add("".join(w[0] for w in words[i:i + n]))
    return out


def lexical_score(query: str, title: str, abstract: str, keywords) -> float:
    """0..1: how many of the query's words appear in the work (title and keywords count more than the abstract)."""
    raw = [t for t in re.findall(r"[a-z0-9]+", (query or "").lower()) if t not in _STOP] or \
          re.findall(r"[a-z0-9]+", (query or "").lower())
    terms = {}
    for r in raw:
        terms.setdefault(_stem(r), r)
    if not terms:
        return 0.0
    kw_list = list(keywords or ())
    kw_text = " ".join(kw_list)
    fields = [(set(stems(title)), 1.0), (set(stems(kw_text)), 1.0), (set(stems(abstract)), 0.7)]
    acro = _acronyms(title, *kw_list)
    total = 0.0
    for stem_, r in terms.items():
        best = max((w * _term_in_field(stem_, vocab) for vocab, w in fields if vocab), default=0.0)
        if best < 0.9 and 2 <= len(r) <= 6 and r in acro:        # 'LMS' -> Learning Management System
            best = 0.9
        total += best
    score = total / len(terms)
    if len(terms) >= 2:                               # the words appear together, in order -> small bonus
        phrase = " ".join(terms)
        for text in (title, kw_text, abstract):
            if phrase in " ".join(stems(text)):
                score += 0.15
                break
    return min(1.0, score)


def hybrid_score(dense: float, lexical: float) -> float:
    return dense if lexical <= 0 else 0.6 * dense + 0.4 * lexical


def rank(query_vec, candidates: list[Candidate], threshold=DEFAULT_THRESHOLD, limit=20, query_text: str = ""):
    """`candidates` MUST already be access- and filter-restricted by the caller.
    Meaning score (best matching piece) is combined with the word-match score when `query_text` is given."""
    if not candidates:
        return []
    hits = []
    for c in candidates:
        d = dense_score(query_vec, c)
        lex = lexical_score(query_text, c.title, c.abstract, c.keywords) if query_text else 0.0
        if d >= threshold or lex >= LEXICAL_MIN:
            hits.append((c.work_id, hybrid_score(d, lex)))
    return sorted(hits, key=lambda t: -t[1])[:limit]


def recommend(target: Candidate, candidates: list[Candidate],
              threshold=DEFAULT_THRESHOLD, count=5):
    """Semantic similarity primary; metadata overlap is a small secondary boost."""
    pool = [c for c in candidates if c.work_id != target.work_id]
    if not pool:
        return []
    sims = cosine_scores(_primary(target), np.vstack([_primary(c) for c in pool]))
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
