from pathlib import Path
from types import SimpleNamespace

from insurance_chatbot import indexing
from insurance_chatbot.indexing import PolicyChunk
from insurance_chatbot.settings import Settings


class FakeEmbeddingAPI:
    def __init__(self) -> None:
        self.calls = 0

    def create(self, *, model: str, input: list[str]) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3]) for _ in input])


class FakeOpenAI:
    def __init__(self) -> None:
        self.embeddings = FakeEmbeddingAPI()


class FakeQdrant:
    def __init__(self) -> None:
        self.exists = False
        self.deleted = 0
        self.upserted: list[object] = []
        self.current_payload: dict[str, object] | None = None

    def collection_exists(self, collection_name: str) -> bool:
        return self.exists

    def create_collection(self, **kwargs: object) -> bool:
        self.exists = True
        return True

    def get_collection(self, collection_name: str) -> SimpleNamespace:
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(
                    vectors=indexing.models.VectorParams(
                        size=3,
                        distance=indexing.models.Distance.COSINE,
                    )
                )
            )
        )

    def delete(self, **kwargs: object) -> None:
        self.deleted += 1

    def delete_collection(self, collection_name: str) -> None:
        self.deleted += 1
        self.exists = False

    def upsert(self, *, points: list[object], **kwargs: object) -> None:
        self.upserted = points
        self.current_payload = points[0].payload

    def scroll(self, **kwargs: object) -> tuple[list[SimpleNamespace], None]:
        if self.current_payload is None:
            return [], None
        return [SimpleNamespace(payload=self.current_payload)], None


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        openai_api_key="test-key",
        chat_model="gpt-test",
        embedding_model="embedding-test",
        qdrant_path=tmp_path / "qdrant",
        qdrant_collection="test-collection",
        top_k=5,
        score_threshold=None,
    )


def test_window_text_enforces_overlap_and_size() -> None:
    text = " ".join(f"word-{index}" for index in range(100))
    chunks = indexing._window_text(text, max_chars=100, overlap_chars=20)
    assert len(chunks) > 1
    assert all(len(chunk) <= 100 for chunk in chunks)


def test_indexing_creates_collection_and_replaces_document(tmp_path: Path, monkeypatch) -> None:
    pdf_path = tmp_path / "POL123.pdf"
    pdf_path.write_bytes(b"placeholder")
    chunks = [
        PolicyChunk(
            point_id="31e6969d-7da4-4b51-b57f-4347d4ec29e5",
            chunk_id="POL123-p001-c0001",
            text="Cobertura hospitalaria.",
            policy_id="POL123",
            filename="POL123.pdf",
            page=1,
            article="Artículo 1",
            document_hash="hash",
        )
    ]
    monkeypatch.setattr(indexing, "extract_policy_chunks", lambda path, **kwargs: chunks)
    qdrant = FakeQdrant()
    openai = FakeOpenAI()

    summary = indexing.index_policies(
        tmp_path,
        settings=_settings(tmp_path),
        openai_client=openai,
        qdrant_client=qdrant,
    )

    assert summary.documents == 1
    assert summary.chunks == 1
    assert qdrant.deleted == 0
    assert len(qdrant.upserted) == 1
    first_run_calls = openai.embeddings.calls

    # A second run with the same PDF and index signature makes no API call.
    indexing.index_policies(
        tmp_path,
        settings=_settings(tmp_path),
        openai_client=openai,
        qdrant_client=qdrant,
    )
    assert openai.embeddings.calls == first_run_calls
    assert qdrant.deleted == 0
