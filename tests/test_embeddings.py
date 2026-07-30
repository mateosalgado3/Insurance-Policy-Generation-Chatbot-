import numpy as np
import pytest

from insurance_chatbot.embeddings import LocalHashingEmbedder, TextEmbedder


def test_local_hashing_implements_embedder_contract() -> None:
    embedder = LocalHashingEmbedder(n_features=128)

    assert isinstance(embedder, TextEmbedder)
    assert embedder.name == "local-hashing"
    assert embedder.dimension == 128


def test_local_hashing_returns_expected_shape_and_dtype() -> None:
    embedder = LocalHashingEmbedder(n_features=128)

    vectors = embedder.encode(
        [
            "La póliza cubre hospitalización.",
            "La póliza excluye enfermedades preexistentes.",
        ]
    )

    assert vectors.shape == (2, 128)
    assert vectors.dtype == np.float32


def test_local_hashing_is_deterministic() -> None:
    embedder = LocalHashingEmbedder(n_features=128)
    texts = ["Cobertura de gastos médicos y hospitalarios."]

    first_result = embedder.encode(texts)
    second_result = embedder.encode(texts)

    np.testing.assert_allclose(first_result, second_result)


def test_related_text_has_higher_similarity() -> None:
    embedder = LocalHashingEmbedder(n_features=256)

    vectors = embedder.encode(
        [
            "La póliza cubre gastos médicos y hospitalización.",
            "El documento describe el domicilio de la aseguradora.",
            "¿La póliza cubre gastos médicos?",
        ]
    )

    relevant_score = float(vectors[0] @ vectors[2])
    unrelated_score = float(vectors[1] @ vectors[2])

    assert relevant_score > unrelated_score


def test_empty_input_returns_empty_matrix() -> None:
    embedder = LocalHashingEmbedder(n_features=64)

    vectors = embedder.encode([])

    assert vectors.shape == (0, 64)


def test_invalid_dimension_is_rejected() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        LocalHashingEmbedder(n_features=0)