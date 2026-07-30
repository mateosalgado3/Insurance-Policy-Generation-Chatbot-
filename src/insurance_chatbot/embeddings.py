"""Embedding providers used by the retrieval layer."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray
from sklearn.feature_extraction.text import HashingVectorizer

EmbeddingMatrix = NDArray[np.float32]


@runtime_checkable
class TextEmbedder(Protocol):
    """Common contract for every text embedding provider."""

    @property
    def name(self) -> str:
        """Return the provider identifier."""

    @property
    def dimension(self) -> int:
        """Return the number of values in each embedding."""

    def encode(self, texts: Sequence[str]) -> EmbeddingMatrix:
        """Convert a sequence of texts into a two-dimensional matrix."""


@dataclass(slots=True)
class LocalHashingEmbedder:
    """Deterministic lexical baseline based on feature hashing."""

    n_features: int = 4096
    _vectorizer: HashingVectorizer = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.n_features <= 0:
            raise ValueError("n_features must be greater than zero")

        self._vectorizer = HashingVectorizer(
            n_features=self.n_features,
            lowercase=True,
            ngram_range=(1, 2),
            alternate_sign=False,
            norm="l2",
            dtype=np.float32,
        )

    @property
    def name(self) -> str:
        return "local-hashing"

    @property
    def dimension(self) -> int:
        return self.n_features

    def encode(self, texts: Sequence[str]) -> EmbeddingMatrix:
        items = list(texts)

        if any(not isinstance(text, str) for text in items):
            raise TypeError("all texts must be strings")

        if not items:
            return np.empty((0, self.dimension), dtype=np.float32)

        sparse_matrix = self._vectorizer.transform(items)

        return sparse_matrix.toarray().astype(np.float32, copy=False)