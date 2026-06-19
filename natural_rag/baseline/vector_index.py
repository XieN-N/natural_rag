from typing import Any, cast

from sentence_transformers import SentenceTransformer, util
import torch


class VectorIndex:
    """Handles embedding generation, storage, and similarity search."""
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self._model = SentenceTransformer(model_name)
        self._items: list[tuple[str, Any]] = []

    def add(self, key: str, texts: list[str]):
        """Encodes texts and stores them associated with the key."""
        if not texts:
            return
        
        embeddings = self._model.encode(texts, convert_to_tensor=True, show_progress_bar=False) # pyright: ignore[reportUnknownMemberType]
        for emb in embeddings:
            self._items.append((key, emb))

    def remove(self, key: str):
        """Removes all vectors associated with the specific key."""
        self._items = [item for item in self._items if item[0] != key]

    def search(self, query: str, n: int) -> list[tuple[float, str]]:
        """
        Embeds query and compares against stored vectors.
        Returns unique keys with their highest found similarity score.
        """
        if not self._items:
            return []

        query_emb = self._model.encode(query, convert_to_tensor=True, show_progress_bar=False) # pyright: ignore[reportUnknownMemberType]
        doc_vecs = [item[1] for item in self._items]
        keys = [item[0] for item in self._items]

        scores = util.cos_sim(query_emb, torch.stack(doc_vecs))[0] # pyright: ignore[reportUnknownMemberType]

        results = sorted(
            zip(cast(list[float], scores.tolist()), keys), # pyright: ignore[reportUnknownMemberType]
            key=lambda x: x[0],
            reverse=True
        )

        final_results: list[tuple[float, str]] = []
        seen: set[str] = set()

        for score, key in results:
            if key not in seen:
                final_results.append((score, key))
                seen.add(key)
                if len(final_results) >= n:
                    break
        
        return final_results