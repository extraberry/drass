"""Embedding model access. Production: Sentence-Transformers from a LOCAL path (no internet).
HashEmbedder is a deterministic bag-of-words stand-in used ONLY by automated tests (EMBEDDER=hash)."""
import hashlib
import logging
import re
import threading
from pathlib import Path
import numpy as np
from ..core.config import get_settings
from ..domain.errors import EmbeddingUnavailable

_STOP = set("a an the of to in on for and or with by is are be that this it as at from using use based into".split())
_lock = threading.Lock()
_embedder = None


class HashEmbedder:
    model_name = "hash-test-embedder"
    dim = 2048

    @staticmethod
    def _stem(t: str) -> str:
        for suf in ("ing", "ed", "es", "s"):
            if t.endswith(suf) and len(t) - len(suf) >= 4:
                return t[: -len(suf)]
        return t

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for tok in re.findall(r"[a-z0-9]+", text.lower()):
                if tok in _STOP:
                    continue
                h = hashlib.md5(self._stem(tok).encode()).digest()
                out[i, int.from_bytes(h[:4], "big") % self.dim] += 1.0 if h[4] & 1 else -1.0
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
        return out


class STEmbedder:
    def __init__(self, path: Path):
        if not path.exists():
            raise EmbeddingUnavailable(f"Embedding model folder not found: {path}. See README (model installation).")
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(str(path), device="cpu")
        except Exception as exc:   # noqa: BLE001
            import traceback
            logging.getLogger("drass.app").error("Embedding model failed to load. Full cause:\n%s", traceback.format_exc())   # shows the hidden original error in the server window
            root = exc
            while root.__cause__ is not None or (root.__context__ is not None and root.__context__ is not root):
                root = root.__cause__ or root.__context__
            raise EmbeddingUnavailable(f"Could not load embedding model: {exc} (root cause: {type(root).__name__}: {root})")
        self.model_name = "all-MiniLM-L6-v2"

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False),
                          dtype=np.float32)


_QCACHE: "OrderedDict[str, np.ndarray]" = None
_qlock = threading.Lock()


def encode_query(text: str) -> np.ndarray:
    """Embed a search query. Recent queries are remembered (LRU, 256) so repeating a search, e.g. during a demo, is instant."""
    global _QCACHE
    from collections import OrderedDict
    with _qlock:
        if _QCACHE is None:
            _QCACHE = OrderedDict()
        hit = _QCACHE.get(text)
        if hit is not None:
            _QCACHE.move_to_end(text)
            return hit
    vec = get_embedder().encode([text])[0]
    with _qlock:
        _QCACHE[text] = vec
        while len(_QCACHE) > 256:
            _QCACHE.popitem(last=False)
    return vec


def warm_up() -> None:
    """Load the model and run one encode so the first real search is fast (called in the background at server start)."""
    import time
    t0 = time.time()
    try:
        get_embedder().encode(["warm up"])
        logging.getLogger("drass.app").info("Embedding model ready in %.1f s", time.time() - t0)
    except Exception as exc:   # noqa: BLE001
        logging.getLogger("drass.app").warning("Embedding model warm-up failed: %s", exc)


def get_embedder():
    global _embedder
    with _lock:
        if _embedder is None:
            s = get_settings()
            _embedder = HashEmbedder() if s.embedder == "hash" else STEmbedder(s.embedding_model_path)
        return _embedder


def set_embedder(e) -> None:
    """Test hook."""
    global _embedder, _QCACHE
    _embedder = e
    _QCACHE = None