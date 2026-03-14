from __future__ import annotations
import logging
from pathlib import Path
from typing import cast
from collections import defaultdict
from itertools import chain, islice

import numpy as np
import pandas as pd
from ragu.models.llm import LLM

from natural_rag.baseline.tree import TreeKnowledgeBase, Excerpt
from natural_rag.baseline.prompts import (
    CLARIFY_PROMPT, INSERT_PROMPT, BUILD_PROMPT, OPTIMIZE_PROMPT, SPLITTING_PROMPT # , KEYWORDS_PROMPT
)
from natural_rag.baseline.struct import (
    Change, Changes, EntriesList, Entry, Names, SplitDocument #, Keywords
)
from natural_rag.baseline.utils import redirect_to_stdout

routines_logger = logging.getLogger("routines")
routines_logger.propagate = False
redirect_to_stdout(routines_logger)

# llm routines

async def split_large_document(llm: LLM, doc: str) -> list[tuple[str, str]]:
    sections = doc.split('\n\n')
    doc_with_marked_sections = '\n\n'.join([
        f'(Sec {i})\n' + sec for i, sec in enumerate(sections)
    ])
    split_rules = cast(SplitDocument, await llm.chat_completion(
        [{"role": "user", "content": SPLITTING_PROMPT.format(
            document_with_marked_sections=doc_with_marked_sections,
        )}],
        output_schema=SplitDocument,
    ))
    if split_rules.parts is None:
        return [('', doc)]

    for part in split_rules.parts or []:
        routines_logger.info(f'Extracted part: {part}')
    
    results: list[tuple[str, str]] = []
    for part_idx, part_info in enumerate(split_rules.parts):
        end_section_idx = (
            split_rules.parts[part_idx + 1].starting_section_id
            if part_idx != len(split_rules.parts) - 1
            else None
        )
        part = '\n\n'.join(sections[part_info.starting_section_id:end_section_idx])
        results.append((part_info.header, part))
    
    return results


# async def extract_keywords(llm: LLM, doc: str) -> Keywords:
#     keywords = cast(Keywords, await llm.chat_completion(
#         [{"role": "user", "content": KEYWORDS_PROMPT.format(document=doc)}],
#         output_schema=Keywords,
#     ))
#     logger.info(f'Main keywords:', keywords.main)
#     logger.info(f'Additional keywords:', keywords.additional)
#     return keywords


async def extract_entries(llm: LLM, doc: str, doc_header: str = '') -> list[Entry]:
    new_entries = cast(EntriesList, await llm.chat_completion(
        [{"role": "user", "content": BUILD_PROMPT.format(
            document_metainfo=doc_header,
            document=doc,
            # excerpt_tree='\n'.join(excerpt.to_lines()),
        )}],
        output_schema=EntriesList,
    )).entries
    routines_logger.info(f'Extracted {len(new_entries)} entries')
    return new_entries


async def select_entries_of_interest(llm: LLM, new_entries: list[Entry], excerpt: Excerpt) -> list[str]:
    names_to_clarify = cast(Names, await llm.chat_completion(
        [{"role": "user", "content": CLARIFY_PROMPT.format(
            new_entries='\n'.join([e.model_dump_json() for e in new_entries]),
            excerpt_tree='\n'.join(excerpt.to_lines()),
        )}],
        output_schema=Names,
    )).names
    routines_logger.info(f'{names_to_clarify=}')
    return names_to_clarify


async def refine_entries(
    llm: LLM, base: TreeKnowledgeBase, new_entries: list[Entry], excerpt: Excerpt, names_to_clarify: list[str]
) -> list[Entry]:
    refined_new_entries = cast(EntriesList, await llm.chat_completion(
        [{"role": "user", "content": INSERT_PROMPT.format(
            new_entries='\n'.join([
                e.model_dump_json()
                for e in new_entries
            ]),
            excerpt_tree='\n'.join(excerpt.to_lines()),
            excerpt_entries='\n'.join([
                base.get_entry(name).model_dump_json()
                for name in names_to_clarify
                if name in base
            ]),
        )}],
        output_schema=EntriesList,
    )).entries

    old_and_new_parents: dict[str, list[str]] = defaultdict(lambda: ['', ''])
    for entry in new_entries:
        old_and_new_parents[entry.name][0] = entry.parent or ''
    for entry in refined_new_entries:
        old_and_new_parents[entry.name][1] = entry.parent or ''
    diff_df = pd.DataFrame([
        {'name': name, 'old_parent': old_parent, 'new_parent': new_parent}
        for name, (old_parent, new_parent) in old_and_new_parents.items()
    ])

    with pd.option_context(
        "display.max_rows", None,
        "display.max_columns", None,
        'display.max_colwidth', None,
        'display.width', None,
    ):
        routines_logger.info(diff_df)

    return refined_new_entries


async def propose_optimizations(llm: LLM, base: TreeKnowledgeBase, excerpt: Excerpt) -> list[Change]:
    excerpt_text = '\n'.join(excerpt.to_lines())
    proposed_changes = cast(Changes, await llm.chat_completion(
        [{"role": "user", "content": OPTIMIZE_PROMPT.format(
            excerpt_tree=excerpt_text,
        )}],
        output_schema=Changes,
    )).changes

    proposed_changes = [
        change for change in proposed_changes
        if base.get_entry(change.entry).parent != change.new_parent
    ]

    diff_df = pd.DataFrame([
        {
            'entry': change.entry,
            'old_parent': base.get_entry(change.entry).parent,
            'new_parent': change.new_parent
        }
        for change in proposed_changes
    ])

    with pd.option_context(
        "display.max_rows", None,
        "display.max_columns", None,
        'display.max_colwidth', None,
        'display.width', None,
    ):
        routines_logger.info(diff_df)
    
    return proposed_changes


# knowledge base routines


# def find_entries_by_keywords(
#     base: TreeKnowledgeBase, keywords: Keywords, additional_multiplier: float = 1 / 3,
# ) -> list[str]:
#     found_relevant_entries: dict[str, float] = defaultdict(float)
#     for query in keywords.main:
#         for score, name in base.search_entries(query, n=50):
#             found_relevant_entries[name] += score
#     for query in keywords.additional:
#         for score, name in base.search_entries(query, n=50):
#             found_relevant_entries[name] += score * additional_multiplier

#     top_relevant_entries = sorted(
#         found_relevant_entries.items(),
#         key=lambda item: -item[1]
#     )[:50]
#     logger.info(f'Top relevant entries from keywords: {top_relevant_entries}')
#     return [name for name, _score in top_relevant_entries]


def find_similar_entries(base: TreeKnowledgeBase, entries: list[Entry]) -> list[str]:
    found_relevant_entries: dict[str, float] = defaultdict(float)
    for entry in entries:
        for query in entry.get_all_fields():
            for score, name in base.search_entries(query, n=50):
                found_relevant_entries[name] += score

    top_relevant_entries = sorted(
        found_relevant_entries.items(),
        key=lambda item: -item[1]
    )[:50]
    routines_logger.info(f'Top relevant entries: {top_relevant_entries}')
    return [name for name, _score in top_relevant_entries]


def insert_entries_inplace(base: TreeKnowledgeBase, new_entries: list[Entry]):
    for entry in new_entries:
        base.add_or_replace_entry(entry)
    base.check_if_entry_tree_valid()
    routines_logger.info(f'Inserted/modified entries: {[entry.name for entry in new_entries]}')


def get_random_excerpt(base: TreeKnowledgeBase, seed: int, n_seed_entries: int = 5, max_siblings: int = 20):
    seed_entries = np.random.default_rng(seed).choice(list(base._entries), n_seed_entries) # pyright: ignore[reportPrivateUsage]
    routines_logger.info(f'Seed entries: {seed_entries}')
    seed_entries_with_parents = list(set([
        e.name for e in chain(*[base.get_full_path(e) for e in seed_entries])
    ]))
    all_entries_to_include = list(set(chain(*[
        islice(base.get_siblings(e), max_siblings) for e in seed_entries_with_parents
    ])))
    excerpt = base.get_excerpt(all_entries_to_include)
    routines_logger.info(f'Total excerpt lines: {len(excerpt.to_lines())}')
    return excerpt


def apply_optimizations_inplace(base: TreeKnowledgeBase, changes: list[Change]):
    for change in changes:
        if change.entry in base and (change.new_parent is None or change.new_parent in base):
            base.get_entry(change.entry).parent = change.new_parent