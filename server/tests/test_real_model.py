"""Runs only when the real Sentence-Transformers model is installed locally. Validates TC-06 with true semantics."""
import pytest
from server.app.core.config import get_settings

st = pytest.importorskip("sentence_transformers")
if not (get_settings().embedding_model_path / "config.json").exists() and not any(get_settings().embedding_model_path.glob("*")):
    pytest.skip("local embedding model not installed", allow_module_level=True)


def test_semantic_similarity_beats_keyword_overlap():
    from server.app.services.embedder import STEmbedder
    import numpy as np
    e = STEmbedder(get_settings().embedding_model_path)
    q, rel, unrel = e.encode(["research projects that use technology to improve student learning",
                              "Development of a mobile quiz application for improving student engagement in science education",
                              "Solar powered irrigation controller for urban gardens"])
    assert float(np.dot(q, rel)) > float(np.dot(q, unrel)) and float(np.dot(q, rel)) > 0.35
