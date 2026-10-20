"""Embedding model access. Production: Sentence-Transformers from a LOCAL path (no internet).
HashEmbedder is a deterministic bag-of-words stand-in used ONLY by automated tests (EMBEDDER=hash)."""
import hashlib
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
            raise EmbeddingUnavailable(f"Could not load embedding model: {exc}")
        self.model_name = "all-MiniLM-L6-v2"

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False),
                          dtype=np.float32)


def get_embedder():
    global _embedder
    with _lock:
        if _embedder is None:
            s = get_settings()
            _embedder = HashEmbedder() if s.embedder == "hash" else STEmbedder(s.embedding_model_path)
        return _embedder


def set_embedder(e) -> None:
    """Test hook."""
    global _embedder
    _embedder = e
