from collections.abc import Iterable
from pathlib import Path

import numpy as np
from prometheus_client import generate_latest

from rag import RagService, _reciprocal_rank_fusion
from sample_documents import SAMPLE_DOCUMENTS


class DeterministicEmbedding:
    @staticmethod
    def embed(texts: list[str]):
        return (np.ones(384, dtype=np.float32) for _ in texts)

    @staticmethod
    def query_embed(query: str):
        return iter([np.ones(384, dtype=np.float32)])


def test_chunks_overlap_and_keep_all_words() -> None:
    words = [f"word{index}" for index in range(500)]

    chunks = RagService._chunk_text(" ".join(words))

    assert len(chunks) == 3
    assert chunks[0].split()[-35:] == chunks[1].split()[:35]
    assert chunks[1].split()[-35:] == chunks[2].split()[:35]
    assert chunks[0].split()[0] == "word0"
    assert chunks[-1].split()[-1] == "word499"


def test_seed_knowledge_base_contains_30_bilingual_articles() -> None:
    assert len(SAMPLE_DOCUMENTS) == 30
    assert {document["language"] for document in SAMPLE_DOCUMENTS} == {"it", "en"}


def test_reciprocal_rank_fusion_rewards_candidates_found_by_both_retrievers() -> None:
    scores = _reciprocal_rank_fusion(
        (["shared", "vector-only"], ["shared", "lexical-only"])
    )

    assert abs(scores["shared"] - 0.4) < 1e-9
    assert scores["shared"] > scores["vector-only"]
    assert scores["shared"] > scores["lexical-only"]


def test_ingest_replaces_document_and_delete_removes_it(tmp_path: Path) -> None:
    service = RagService(data_dir=tmp_path, qdrant_url=":memory:")
    service._embedder = DeterministicEmbedding()
    content = b"Payroll password reset policy for employees."

    first = service.ingest("C:\\upload\\guide.txt", "Guide", "Account", "en", content)
    second = service.ingest("guide.txt", "Updated guide", "Account", "en", b"Updated password policy.")

    assert first["document_id"] == second["document_id"]
    assert first["version"] == 1
    assert second["version"] == 2
    assert service.list_documents()[0]["title"] == "Updated guide"
    assert service.delete_document(second["document_id"])
    assert service.list_documents() == []
    assert not service.delete_document(second["document_id"])


def test_deleted_sample_documents_are_not_reseeded_on_restart(tmp_path: Path) -> None:
    service = RagService(data_dir=tmp_path, qdrant_url=":memory:")
    service._embedder = DeterministicEmbedding()
    article = SAMPLE_DOCUMENTS[:1]

    assert service.seed_if_empty(article) == 1
    document_id = service.list_documents()[0]["document_id"]
    assert service.delete_document(document_id)
    assert service.seed_if_empty(article) == 0
    assert service.list_documents() == []


def test_search_metrics_count_results_without_recording_the_query(tmp_path: Path) -> None:
    service = RagService(data_dir=tmp_path, qdrant_url=":memory:")
    service._embedder = DeterministicEmbedding()
    service._reranker = DeterministicReranker()
    service.ingest("guide.txt", "Guide", "Account", "en", b"Password reset instructions.")

    assert service.search("password reset")

    metrics = generate_latest().decode("utf-8")
    assert 'service_desk_rag_searches_total{outcome="results"}' in metrics
    assert "password reset" not in metrics


class DeterministicReranker:
    def rerank(self, query: str, documents: Iterable[str]) -> list[float]:
        assert query == "password reset"
        return [1.0 if "preferred" in document else 0.0 for document in documents]


def test_hybrid_search_reranks_retrieved_candidates(tmp_path: Path) -> None:
    service = RagService(data_dir=tmp_path, qdrant_url=":memory:")
    service._embedder = DeterministicEmbedding()
    service._reranker = DeterministicReranker()
    service.ingest("first.txt", "First", "Account", "en", b"Password reset steps for an account.")
    service.ingest(
        "preferred.txt",
        "Preferred",
        "Account",
        "en",
        b"Password reset preferred steps for an account.",
    )

    hits = service.search("password reset")

    assert [hit.source for hit in hits[:2]] == ["preferred.txt", "first.txt"]
    assert hits[0].score == 1.0


def test_reranking_can_be_disabled_without_loading_a_model(tmp_path: Path) -> None:
    service = RagService(data_dir=tmp_path, qdrant_url=":memory:", reranking_enabled=False)
    service._embedder = DeterministicEmbedding()
    service.ingest("guide.txt", "Guide", "Account", "en", b"Password reset instructions.")

    assert service.search("password reset")
    assert service._reranker is None
