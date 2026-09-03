"""Collection-name prefixing for Wikontic storage backends.

Wikontic hardcodes its collection names inside the aligners
(``wikontic.utils.dynamic_aligner.Aligner`` / ``structured_aligner.Aligner``):
``entity_aliases``, ``property_aliases``, ``initial_triplets``, ``triplets``,
``filtered_triplets``, ``ontology_filtered_triplets``, ``entity_types``,
``entity_type_aliases``, ``properties``. There is no parameter to change them,
so two indexes built into the same MongoDB database (or the same Qdrant
instance) would silently share — and cross-contaminate — the same collections.

``PrefixedBackend`` wraps a backend created by ``wikontic.db.factory.create_backend``
and rewrites the collection name on every call. It works for both backends
because ``wikontic.db.interfaces.StorageBackend`` is uniform: every method takes
``collection_name`` first, except ``list_collection_names()`` (filtered and
stripped here) and ``vector_search(VectorQuery)`` (the collection is a field on
the query object).

Typical use::

    backend = create_backend("qdrant", qdrant_url=url)
    backend = PrefixedBackend(backend, "musique__gigachat__structured__corpus")
    create_triplets_database(storage_backend=backend)
"""
from __future__ import annotations

import dataclasses
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

SEPARATOR = "__"

#: Field on ``wikontic.db.interfaces.VectorQuery`` holding the collection name.
#: Probed at runtime so a rename upstream surfaces as a clear error.
_COLLECTION_FIELD_CANDIDATES = ("collection_name", "collection")


def sanitize_prefix(name: str) -> str:
    """Make ``name`` safe as part of a Mongo/Qdrant collection name."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")


class _VectorSafeCollection:
    """Drops alias documents whose embedding is missing.

    ``Aligner.add_entity`` / ``add_property`` store
    ``"alias_text_embedding": self.get_embedding(alias)``, and
    ``get_embedding`` returns ``None`` for an empty string
    (``wikontic/utils/dynamic_aligner.py``). An LLM that emits a triplet with an
    empty subject or object therefore produces an alias document with no vector.

    Under MongoDB that is a harmless null field. Under Qdrant every point must
    carry a vector of the collection's size, so ``_upsert_documents`` infers the
    size from the batch, finds no list, falls back to ``1``, and
    ``_ensure_vector_size`` "repairs" the 768-dim collection by **deleting it**
    and re-uploading every payload in a single request. Past a few thousand
    embeddings that request exceeds Qdrant's size limit, the upload fails, and
    the collection stays empty -- while the exception is swallowed upstream and
    the run still reports ``failures: 0``.

    That is how this bundle lost 90% of ``entity_aliases`` during indexing (23
    empty-object triplets, three of them past the limit). Refusing the document
    is enough to keep the whole chain from starting: no null vector, no size
    collapse, no rebuild.
    """

    def __init__(self, collection: Any, name: str):
        self._collection = collection
        self._name = name

    @staticmethod
    def _has_vector(document: Any) -> bool:
        if not isinstance(document, dict) or "alias_text_embedding" not in document:
            return True  # not an alias document; nothing to check
        embedding = document["alias_text_embedding"]
        return isinstance(embedding, list) and len(embedding) > 0

    def insert_one(self, document: Any) -> None:
        if not self._has_vector(document):
            logger.warning(
                "Dropping alias %r for %r: embedder returned no vector "
                "(inserting it would delete the collection)",
                document.get("alias"), self._name,
            )
            return
        return self._collection.insert_one(document)

    def insert_many(self, documents: Any) -> None:
        docs = list(documents)  # may be a generator; only iterate once
        kept = [doc for doc in docs if self._has_vector(doc)]
        if len(kept) != len(docs):
            logger.warning(
                "Dropping %d alias document(s) for %r: embedder returned no vector",
                len(docs) - len(kept), self._name,
            )
        if kept:
            return self._collection.insert_many(kept)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._collection, item)

    def __repr__(self) -> str:
        return f"_VectorSafeCollection({self._collection!r})"


class PrefixedBackend:
    """Namespaces every collection of ``backend`` under ``prefix``."""

    def __init__(self, backend: Any, prefix: str):
        prefix = sanitize_prefix(prefix)
        if not prefix:
            raise ValueError("prefix must contain at least one usable character")
        self._backend = backend
        self.prefix = prefix

    # ── name mapping ───────────────────────────────────────────────

    def _c(self, collection_name: str) -> str:
        return f"{self.prefix}{SEPARATOR}{collection_name}"

    def _strip(self, collection_name: str) -> str | None:
        head = f"{self.prefix}{SEPARATOR}"
        return collection_name[len(head):] if collection_name.startswith(head) else None

    # ── StorageBackend protocol ────────────────────────────────────

    def get_collection(self, collection_name: str) -> Any:
        return _VectorSafeCollection(
            self._backend.get_collection(self._c(collection_name)),
            self._c(collection_name),
        )

    def ensure_collection(self, collection_name: str) -> None:
        self._backend.ensure_collection(self._c(collection_name))

    def drop_collection(self, collection_name: str) -> None:
        self._backend.drop_collection(self._c(collection_name))

    def create_indexes(self, collection_name: str, *args: Any, **kwargs: Any) -> None:
        self._backend.create_indexes(self._c(collection_name), *args, **kwargs)

    def ensure_vector_index(
        self,
        collection_name: str,
        index_name: str,
        vector_field: str,
        num_dimensions: int,
        similarity: str = "cosine",
        token_fields: list[str] | None = None,
        recreate: bool = False,
    ) -> Any:
        """Declare the vector index, without rebuilding one that is already there.

        ``QdrantBackend.ensure_vector_index`` discards its ``recreate`` argument
        and always calls ``_recreate_collection_vectors``, which reads the
        payloads back, **deletes the collection**, recreates it empty and
        re-upserts everything in a single request. ``create_triplets_database``
        runs from the ``WikonticPipeline`` constructor, so this fires on
        answer-only runs too: a graph exported off the cluster is destroyed and
        rebuilt merely to ask questions of it. On ``property_aliases`` (3540 x
        768 floats, ~115 MB) the re-upsert exceeds Qdrant's request limit and
        the collection is left empty -- which is how one was lost here.

        Nothing needs rebuilding when the collection already carries the vector
        being declared. The only lasting effect of the upstream call is the
        ``_vector_config`` entry that ``vector_search`` reads back, so we write
        it directly and skip the destructive part.
        """
        name = self._c(collection_name)
        if not recreate and self._vector_index_matches(name, index_name, num_dimensions):
            self._backend._vector_config[name] = (index_name, num_dimensions)
            if token_fields:
                self._backend.create_indexes(name, [[field] for field in token_fields])
            logger.info("Vector index %r already on %r; not rebuilding", index_name, name)
            return None
        return self._backend.ensure_vector_index(
            name, index_name, vector_field, num_dimensions,
            similarity, token_fields, recreate,
        )

    def upsert_many(self, collection_name: str, *args: Any, **kwargs: Any) -> Any:
        return self._backend.upsert_many(self._c(collection_name), *args, **kwargs)

    def match_documents(self, collection_name: str, *args: Any, **kwargs: Any) -> Any:
        return self._backend.match_documents(self._c(collection_name), *args, **kwargs)

    def list_collection_names(self) -> list[str]:
        names = (self._strip(name) for name in self._backend.list_collection_names())
        return [name for name in names if name is not None]

    def vector_search(self, query: Any) -> Any:
        return self._backend.vector_search(self._prefix_query(query))

    # ── helpers ────────────────────────────────────────────────────

    def _vector_index_matches(
        self, name: str, index_name: str, num_dimensions: int
    ) -> bool:
        """True when ``name`` already exists carrying exactly this named vector.

        Qdrant-only: Mongo keeps no comparable server-side state, so there we
        return False and let the wrapped backend do whatever it did before.
        """
        client = getattr(self._backend, "client", None)
        if client is None or not hasattr(self._backend, "_vector_config"):
            return False
        try:
            vectors = client.get_collection(name).config.params.vectors
        except Exception:
            # Missing collection (the ordinary first-index case) or a client
            # that cannot answer: either way, defer to the real implementation.
            return False
        if not isinstance(vectors, dict):
            # Unnamed vector. Upstream would give it a name, so that is a real
            # difference and the rebuild is warranted.
            return False
        params = vectors.get(index_name)
        return params is not None and params.size == num_dimensions

    def _prefix_query(self, query: Any) -> Any:
        for field_name in _COLLECTION_FIELD_CANDIDATES:
            if hasattr(query, field_name):
                current = getattr(query, field_name)
                prefixed = self._c(current)
                if dataclasses.is_dataclass(query):
                    return dataclasses.replace(query, **{field_name: prefixed})
                setattr(query, field_name, prefixed)
                return query
        raise AttributeError(
            "VectorQuery has no known collection field "
            f"(tried {_COLLECTION_FIELD_CANDIDATES}); wikontic's db/interfaces.py "
            "changed and natural_rag/wikontic_prefix.py needs updating."
        )

    def __getattr__(self, item: str) -> Any:
        # Anything not part of the protocol (e.g. QdrantBackend.client) passes
        # straight through to the wrapped backend.
        return getattr(self._backend, item)

    def __repr__(self) -> str:
        return f"PrefixedBackend(prefix={self.prefix!r}, backend={self._backend!r})"
