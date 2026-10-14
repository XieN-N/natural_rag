"""Is a Wikontic graph actually usable, or only present?

Wikontic reports an indexing run as ``failures: 0, status: done`` even when its
Qdrant adapter has destroyed a collection mid-run: any exception raised while a
triplet is processed is caught, stored as ``exception_text`` on the triplet, and
the triplet is filed under ``filtered_triplets``
(``wikontic/utils/inference_with_db.py``). A wiped entity index therefore looks
like "one triplet was filtered".

That is how ``graphrag_bench_medical`` shipped with 272 alias labels for 4717
entities -- 5.8% of the graph reachable from a question -- and was only noticed
weeks later, when 17 of 20 smoke answers came back empty.

The numbers that would have caught it on day one are all cheap and need no LLM:

``entity_coverage``
    Distinct subjects/objects in ``triplets`` that have an ``entity_aliases``
    label. Question linking searches that collection and nothing else, so
    entities missing from it are unreachable at any hop depth.

``property_coverage``
    The same for relations against ``property_aliases``.

``swallowed_exceptions``
    ``filtered_triplets`` carrying an ``exception_text``. Zero is the expected
    value; ``larger than allowed`` among them means a collection was dropped and
    its re-upload rejected.
"""
from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass, field

import httpx

from natural_rag.url_guard import assert_http_url

from natural_rag.wikontic_prefix import sanitize_prefix

SCROLL_PAGE = 1000


@dataclass
class GraphHealth:
    """Counts describing one indexed graph. All fields are cheap to compute."""

    triplets: int = 0
    initial_triplets: int = 0
    distinct_entities: int = 0
    distinct_relations: int = 0
    entity_alias_points: int = 0
    entity_alias_labels: int = 0
    property_alias_points: int = 0
    property_alias_labels: int = 0
    filtered_triplets: int = 0
    swallowed_exceptions: int = 0
    wiped_collection_evidence: int = 0
    missing_collections: list[str] = field(default_factory=list)

    @property
    def entity_coverage(self) -> float:
        if not self.distinct_entities:
            return 0.0
        return self.entity_alias_labels / self.distinct_entities

    @property
    def property_coverage(self) -> float:
        if not self.distinct_relations:
            return 0.0
        return self.property_alias_labels / self.distinct_relations

    def problems(self, min_coverage: float = 0.95) -> list[str]:
        """Reasons this graph should not be used as it stands."""
        issues: list[str] = []
        if self.missing_collections:
            issues.append(
                "коллекции отсутствуют или пусты: " + ", ".join(self.missing_collections)
            )
        if not self.triplets:
            issues.append("в графе нет триплетов")
        if self.distinct_entities and self.entity_coverage < min_coverage:
            issues.append(
                f"покрытие сущностей {self.entity_coverage:.1%} "
                f"({self.entity_alias_labels} из {self.distinct_entities}) — "
                f"линковка вопроса видит только эту долю графа"
            )
        if self.distinct_relations and self.property_coverage < min_coverage:
            issues.append(
                f"покрытие отношений {self.property_coverage:.1%} "
                f"({self.property_alias_labels} из {self.distinct_relations})"
            )
        return issues

    def warnings(self) -> list[str]:
        """Facts worth knowing that do not by themselves condemn the index.

        A collection wipe is recorded in ``filtered_triplets`` forever, so a
        bundle repaired by ``backfill_entity_aliases.py`` still carries the
        evidence. Treating that as fatal would condemn a working index; what it
        actually means is that the surviving aliases are partly reconstructed.
        """
        notes: list[str] = []
        if self.wiped_collection_evidence:
            notes.append(
                f"{self.wiped_collection_evidence} исключений вида 'larger than "
                f"allowed': во время индексации коллекцию удаляли и не смогли "
                f"перезалить. Покрытие сейчас в норме, значит справочник был "
                f"восстановлен — алиасы частично реконструированы, а не исходные"
            )
        elif self.swallowed_exceptions:
            notes.append(
                f"{self.swallowed_exceptions} исключений проглочено при "
                f"индексации; загляните в filtered_triplets"
            )
        return notes

    def as_summary(self) -> dict:
        """The subset worth recording in ``index_summary.json``."""
        return {
            "distinct_entities": self.distinct_entities,
            "entity_alias_labels": self.entity_alias_labels,
            "entity_coverage": round(self.entity_coverage, 4),
            "distinct_relations": self.distinct_relations,
            "property_alias_labels": self.property_alias_labels,
            "property_coverage": round(self.property_coverage, 4),
            "filtered_triplets": self.filtered_triplets,
            "swallowed_exceptions": self.swallowed_exceptions,
            "wiped_collection_evidence": self.wiped_collection_evidence,
        }


def scroll_payloads(url: str, collection: str) -> list[dict] | None:
    """Every payload in ``collection``, or None when it does not exist."""
    assert_http_url(url, what="Qdrant URL")
    payloads: list[dict] = []
    offset = None
    with httpx.Client(timeout=300) as client:
        while True:
            body: dict = {"limit": SCROLL_PAGE, "with_payload": True, "with_vector": False}
            if offset is not None:
                body["offset"] = offset
            response = client.post(
                f"{url}/collections/{urllib.parse.quote(collection)}/points/scroll",
                json=body,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            result = response.json()["result"]
            payloads.extend(p["payload"] for p in result["points"] if p.get("payload"))
            offset = result.get("next_page_offset")
            if offset is None:
                return payloads


def collect(url: str, prefix: str) -> GraphHealth:
    """Measure the graph namespaced under ``prefix`` in the Qdrant at ``url``.

    ``prefix`` is sanitized here rather than trusted: callers pass a RUN_ID
    straight from the shell (``validate_index.py --collection-prefix $RUN_ID``,
    stage 5 of the job scripts), while the collections were created through
    :class:`PrefixedBackend`, which rewrites everything outside ``[A-Za-z0-9_-]``
    to ``_``. A model name with a dot in it — ``meno-lite-0.1``,
    ``Qwen2.5-7B-Instruct`` — otherwise makes a perfectly good index read as
    entirely missing.
    """
    prefix = sanitize_prefix(prefix)
    health = GraphHealth()

    def read(name: str, required: bool) -> list[dict]:
        rows = scroll_payloads(url, f"{prefix}__{name}")
        if rows is None or (required and not rows):
            health.missing_collections.append(name)
            return []
        return rows

    triplets = read("triplets", required=True)
    health.triplets = len(triplets)
    health.initial_triplets = len(read("initial_triplets", required=True))

    entities: set[str] = set()
    relations: set[str] = set()
    for triplet in triplets:
        for field_name in ("subject", "object"):
            value = triplet.get(field_name)
            if isinstance(value, str) and value:
                entities.add(value)
        relation = triplet.get("relation")
        if isinstance(relation, str) and relation:
            relations.add(relation)
    health.distinct_entities = len(entities)
    health.distinct_relations = len(relations)

    entity_aliases = read("entity_aliases", required=False)
    health.entity_alias_points = len(entity_aliases)
    health.entity_alias_labels = len(
        {a["label"] for a in entity_aliases if a.get("label")} & entities
    )

    property_aliases = read("property_aliases", required=False)
    health.property_alias_points = len(property_aliases)
    health.property_alias_labels = len(
        {a["label"] for a in property_aliases if a.get("label")} & relations
    )

    filtered = read("filtered_triplets", required=False)
    health.filtered_triplets = len(filtered)
    for triplet in filtered:
        text = triplet.get("exception_text")
        if not text:
            continue
        health.swallowed_exceptions += 1
        if "larger than allowed" in str(text):
            health.wiped_collection_evidence += 1

    return health


def collect_from_backend(backend, prefix: str) -> GraphHealth | None:
    """Same measurement from a live ``PrefixedBackend``, or None if unreachable.

    Used at the end of an indexing run, where the Qdrant URL is not to hand but
    the backend is. Returns None rather than raising: a diagnostic must never be
    the reason a 22-hour job reports failure.
    """
    # QdrantClient -> QdrantRemote.rest_uri. Absent for the in-memory client,
    # which has no HTTP endpoint to scroll.
    client = getattr(backend, "client", None)
    url = getattr(getattr(client, "_client", None), "rest_uri", None)
    if not url:
        return None
    try:
        return collect(str(url).rstrip("/"), prefix)
    except Exception:
        return None
