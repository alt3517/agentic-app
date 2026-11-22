from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import re
import sqlite3
from threading import Lock
from time import perf_counter
import uuid
from typing import Any, Iterable, Iterator

from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from qdrant_client import QdrantClient, models
from docx import Document
from docx.opc.exceptions import PackageNotFoundError

from telemetry import RAG_SEARCH_DURATION, RAG_SEARCHES


COLLECTION = "service-desk-knowledge"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_SIZE = 384
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
RRF_K = 5
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3-int8"


def _reciprocal_rank_fusion(ranked_lists: Iterable[Iterable[str]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranked_list in ranked_lists:
        for rank, candidate_id in enumerate(ranked_list):
            scores[candidate_id] = scores.get(candidate_id, 0.0) + 1 / (RRF_K + rank)
    return scores


@dataclass(frozen=True)
class RagHit:
    chunk_id: str
    text: str
    title: str
    source: str
    language: str
    category: str
    page: int | None
    score: float
    version: int

    def citation(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "source": self.source,
            "page": self.page,
            "version": self.version,
            "chunk_id": self.chunk_id,
        }


class RagService:
    def __init__(
        self,
        data_dir: str | Path | None = None,
        qdrant_url: str | None = None,
        embedding_model: str = EMBEDDING_MODEL,
        reranking_enabled: bool | None = None,
    ) -> None:
        self.data_dir = Path(data_dir or os.getenv("DATA_DIR", "data"))
        self.qdrant_url = qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.embedding_model_name = embedding_model
        configured_reranking = os.getenv("RERANKING_ENABLED", "true").strip().lower()
        if reranking_enabled is None and configured_reranking not in {"true", "false"}:
            raise ValueError("RERANKING_ENABLED must be 'true' or 'false'.")
        self.reranking_enabled = (
            configured_reranking == "true" if reranking_enabled is None else reranking_enabled
        )
        self._embedder: TextEmbedding | None = None
        self._reranker: TextCrossEncoder | None = None
        self._reranker_lock = Lock()
        self._client: QdrantClient | None = None
        self._database_path = self.data_dir / "knowledge.db"
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    language TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_bytes BLOB NOT NULL,
                    extension TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    chunk_id UNINDEXED,
                    document_id UNINDEXED,
                    title,
                    source UNINDEXED,
                    language UNINDEXED,
                    category UNINDEXED,
                    text,
                    page UNINDEXED,
                    version UNINDEXED,
                    tokenize='unicode61 remove_diacritics 2'
                )
                """
            )

        if self.qdrant_url == ":memory:":
            self._client = QdrantClient(":memory:")
        else:
            self._client = QdrantClient(url=self.qdrant_url, timeout=30)

        if not self._client.collection_exists(COLLECTION):
            self._client.create_collection(
                collection_name=COLLECTION,
                vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
            )
        self._initialized = True

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self.initialize()
        client = self._client
        if client is None:
            raise RuntimeError("Qdrant client initialization failed.")
        return client

    @property
    def embedder(self) -> TextEmbedding:
        if self._embedder is None:
            self._embedder = TextEmbedding(
                model_name=self.embedding_model_name,
                cache_dir=os.getenv("EMBEDDING_CACHE_DIR", str(self.data_dir / "models")),
            )
        return self._embedder

    @property
    def reranker(self) -> TextCrossEncoder:
        if self._reranker is None:
            with self._reranker_lock:
                if self._reranker is None:
                    self._reranker = TextCrossEncoder(
                        model_name=os.getenv("RERANKER_MODEL", DEFAULT_RERANKER_MODEL),
                        cache_dir=os.getenv("EMBEDDING_CACHE_DIR", str(self.data_dir / "models")),
                    )
        return self._reranker

    def seed_if_empty(self, documents: Iterable[dict[str, str]]) -> int:
        self.initialize()
        seed_documents = list(documents)
        sample_sources = {document["source"] for document in seed_documents}
        with self._connect() as db:
            marker = db.execute(
                "SELECT value FROM system_state WHERE key = 'sample_seed_complete'"
            ).fetchone()
            if marker is not None:
                return 0
            existing_sources = {row[0] for row in db.execute("SELECT source FROM documents").fetchall()}
            if existing_sources and not existing_sources.intersection(sample_sources):
                db.execute(
                    "INSERT INTO system_state(key, value) VALUES('sample_seed_complete', 'true')"
                )
                return 0

        count = 0
        for document in seed_documents:
            if document["source"] in existing_sources:
                continue
            content = document["content"].encode("utf-8")
            self.ingest(
                source=document["source"],
                title=document["title"],
                category=document["category"],
                language=document["language"],
                file_bytes=content,
                extension=".md",
            )
            count += 1
        with self._connect() as db:
            db.execute(
                "INSERT INTO system_state(key, value) VALUES('sample_seed_complete', 'true')"
            )
        return count

    def vector_count(self) -> int:
        return int(self.client.count(collection_name=COLLECTION, exact=True).count)

    def chunk_count(self) -> int:
        self.initialize()
        with self._connect() as db:
            return int(db.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0])

    def ingest(
        self,
        source: str,
        title: str,
        category: str,
        language: str,
        file_bytes: bytes,
        extension: str | None = None,
    ) -> dict[str, Any]:
        self.initialize()
        safe_source = Path(source.replace("\\", "/")).name.strip()
        suffix = (extension or Path(safe_source).suffix).lower()
        if not safe_source or suffix not in ALLOWED_EXTENSIONS:
            raise ValueError("Only TXT, Markdown, PDF, and DOCX documents are supported.")
        if len(file_bytes) > MAX_DOCUMENT_BYTES:
            raise ValueError("Documents must be 5 MB or smaller.")
        if language not in {"it", "en"}:
            raise ValueError("Language must be 'it' or 'en'.")

        pages = self._extract_pages(file_bytes, suffix)
        if not any(text.strip() for _, text in pages):
            raise ValueError("The uploaded document contains no extractable text.")

        document_id = sha256(safe_source.casefold().encode("utf-8")).hexdigest()[:32]
        file_hash = sha256(file_bytes).hexdigest()
        with self._connect() as db:
            previous = db.execute(
                "SELECT version FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            version = 1 if previous is None else int(previous[0]) + 1

        chunks: list[tuple[int | None, str]] = []
        for page_number, text in pages:
            chunks.extend((page_number, chunk) for chunk in self._chunk_text(text))
        if not chunks:
            raise ValueError("The document did not produce any indexable text chunks.")

        vectors = list(self.embedder.embed([chunk for _, chunk in chunks]))
        points: list[models.PointStruct] = []
        fts_rows: list[tuple[Any, ...]] = []
        title = title.strip() or Path(safe_source).stem
        for index, ((page, chunk), vector) in enumerate(zip(chunks, vectors, strict=True)):
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}:{version}:{index}"))
            payload = {
                "document_id": document_id,
                "chunk_id": chunk_id,
                "title": title,
                "source": safe_source,
                "language": language,
                "category": category.strip()[:80] or "General",
                "page": page,
                "version": version,
                "text": chunk,
            }
            points.append(models.PointStruct(id=chunk_id, vector=vector.tolist(), payload=payload))
            fts_rows.append(
                (chunk_id, document_id, title, safe_source, language, payload["category"], chunk, page, version)
            )

        self.client.delete(
            collection_name=COLLECTION,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))]
                )
            ),
            wait=True,
        )
        with self._connect() as db:
            db.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document_id,))
            db.execute(
                """
                INSERT INTO documents(id, source, title, category, language, version, file_hash, file_bytes, extension, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    source=excluded.source,
                    title=excluded.title,
                    category=excluded.category,
                    language=excluded.language,
                    version=excluded.version,
                    file_hash=excluded.file_hash,
                    file_bytes=excluded.file_bytes,
                    extension=excluded.extension,
                    updated_at=excluded.updated_at
                """,
                (
                    document_id,
                    safe_source,
                    title,
                    category.strip()[:80] or "General",
                    language,
                    version,
                    file_hash,
                    file_bytes,
                    suffix,
                ),
            )
            db.executemany(
                """
                INSERT INTO chunks_fts(chunk_id, document_id, title, source, language, category, text, page, version)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                fts_rows,
            )

        self.client.upsert(collection_name=COLLECTION, points=points, wait=True)
        return {"document_id": document_id, "source": safe_source, "version": version, "chunks": len(chunks)}

    def delete_document(self, document_id: str) -> bool:
        self.initialize()
        with self._connect() as db:
            exists = db.execute("SELECT 1 FROM documents WHERE id = ?", (document_id,)).fetchone()
        if exists is None:
            return False

        self.client.delete(
            collection_name=COLLECTION,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))]
                )
            ),
            wait=True,
        )
        with self._connect() as db:
            db.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document_id,))
            db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        return True

    def reindex(self) -> int:
        self.initialize()
        with self._connect() as db:
            documents = db.execute(
                "SELECT source, title, category, language, file_bytes, extension FROM documents"
            ).fetchall()
        for source, title, category, language, file_bytes, extension in documents:
            self.ingest(source, title, category, language, file_bytes, extension)
        return len(documents)

    def list_documents(self) -> list[dict[str, Any]]:
        self.initialize()
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, source, title, category, language, version, updated_at FROM documents ORDER BY source"
            ).fetchall()
        return [
            {
                "document_id": row[0],
                "source": row[1],
                "title": row[2],
                "category": row[3],
                "language": row[4],
                "version": row[5],
                "updated_at": row[6],
            }
            for row in rows
        ]

    def search(
        self,
        query: str,
        limit: int = 5,
        language: str | None = None,
        category: str | None = None,
    ) -> list[RagHit]:
        started_at = perf_counter()
        outcome = "error"
        try:
            hits = self._search(query, limit, language, category)
            outcome = "results" if hits else "empty"
            return hits
        finally:
            RAG_SEARCHES.labels(outcome=outcome).inc()
            RAG_SEARCH_DURATION.observe(perf_counter() - started_at)

    def _search(
        self,
        query: str,
        limit: int,
        language: str | None,
        category: str | None,
    ) -> list[RagHit]:
        self.initialize()
        normalized_query = query.strip()
        if not normalized_query:
            return []
        limit = min(max(limit, 1), 10)

        filters: list[models.FieldCondition] = []
        if language in {"it", "en"}:
            filters.append(models.FieldCondition(key="language", match=models.MatchValue(value=language)))
        if category:
            filters.append(models.FieldCondition(key="category", match=models.MatchValue(value=category)))
        query_filter = models.Filter(must=filters) if filters else None

        query_vector = next(self.embedder.query_embed(normalized_query)).tolist()
        vector_points = self.client.query_points(
            collection_name=COLLECTION,
            query=query_vector,
            query_filter=query_filter,
            limit=max(20, limit * 4),
            score_threshold=0.25,
            with_payload=True,
        ).points

        tokens = re.findall(r"[\w]{2,}", normalized_query, flags=re.UNICODE)[:24]
        lexical_rows: list[tuple[Any, ...]] = []
        if tokens:
            fts_query = " OR ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)
            clauses = ["chunks_fts MATCH ?"]
            values: list[Any] = [fts_query]
            if language in {"it", "en"}:
                clauses.append("language = ?")
                values.append(language)
            if category:
                clauses.append("category = ?")
                values.append(category)
            values.append(max(20, limit * 4))
            with self._connect() as db:
                lexical_rows = db.execute(
                    f"""
                    SELECT chunk_id, document_id, title, source, language, category, text, page, version
                    FROM chunks_fts
                    WHERE {' AND '.join(clauses)}
                    ORDER BY bm25(chunks_fts)
                    LIMIT ?
                    """,
                    values,
                ).fetchall()

        candidates: dict[str, dict[str, Any]] = {}
        vector_ids: list[str] = []
        for point in vector_points:
            payload = point.payload or {}
            chunk_id = str(payload.get("chunk_id", point.id))
            candidates[chunk_id] = {"payload": payload}
            vector_ids.append(chunk_id)

        lexical_ids: list[str] = []
        for row in lexical_rows:
            chunk_id = row[0]
            candidates.setdefault(
                chunk_id,
                {
                    "payload": {
                        "chunk_id": row[0],
                        "document_id": row[1],
                        "title": row[2],
                        "source": row[3],
                        "language": row[4],
                        "category": row[5],
                        "text": row[6],
                        "page": row[7],
                        "version": row[8],
                    },
                },
            )
            lexical_ids.append(chunk_id)

        scores = _reciprocal_rank_fusion((vector_ids, lexical_ids))
        candidate_limit = max(20, limit * 4)
        rerank_candidates = sorted(
            candidates.items(),
            key=lambda item: scores[item[0]],
            reverse=True,
        )[:candidate_limit]
        if not rerank_candidates:
            return []

        if self.reranking_enabled:
            rerank_scores = list(
                self.reranker.rerank(
                    normalized_query,
                    (str(item["payload"]["text"]) for _, item in rerank_candidates),
                )
            )
            if len(rerank_scores) != len(rerank_candidates):
                raise RuntimeError("The reranker returned a different number of scores than candidates.")
            ranked = sorted(
                zip(rerank_candidates, rerank_scores, strict=True),
                key=lambda item: item[1],
                reverse=True,
            )[:limit]
        else:
            ranked = [(candidate, scores[candidate[0]]) for candidate in rerank_candidates[:limit]]
        return [
            RagHit(
                chunk_id=str(item["payload"]["chunk_id"]),
                text=str(item["payload"]["text"]),
                title=str(item["payload"]["title"]),
                source=str(item["payload"]["source"]),
                language=str(item["payload"]["language"]),
                category=str(item["payload"]["category"]),
                page=item["payload"].get("page"),
                score=float(rerank_score),
                version=int(item["payload"]["version"]),
            )
            for (chunk_id, item), rerank_score in ranked
        ]

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self._database_path)
        db.execute("PRAGMA foreign_keys = ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _extract_pages(file_bytes: bytes, extension: str) -> list[tuple[int | None, str]]:
        if extension in {".txt", ".md"}:
            try:
                return [(None, file_bytes.decode("utf-8-sig"))]
            except UnicodeDecodeError as exc:
                raise ValueError("Text documents must be valid UTF-8.") from exc
        if extension == ".pdf":
            try:
                reader = PdfReader(BytesIO(file_bytes))
                return [
                    (page_index + 1, page.extract_text() or "")
                    for page_index, page in enumerate(reader.pages)
                ]
            except PdfReadError as exc:
                raise ValueError("The PDF document is invalid or encrypted.") from exc
        if extension == ".docx":
            try:
                document = Document(BytesIO(file_bytes))
                paragraphs = "\n".join(paragraph.text for paragraph in document.paragraphs)
                return [(None, paragraphs)]
            except PackageNotFoundError as exc:
                raise ValueError("The DOCX document is invalid.") from exc
        raise ValueError("The uploaded file type is not supported.")

    @staticmethod
    def _chunk_text(text: str, max_words: int = 220, overlap_words: int = 35) -> list[str]:
        words = text.split()
        if not words:
            return []
        chunks: list[str] = []
        start = 0
        while start < len(words):
            end = min(start + max_words, len(words))
            chunk = " ".join(words[start:end]).strip()
            if chunk:
                chunks.append(chunk)
            if end == len(words):
                break
            start = end - overlap_words
        return chunks
