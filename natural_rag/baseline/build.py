from __future__ import annotations
from pathlib import Path

from ragu.models.llm import LLM

from natural_rag.baseline.tree import TreeKnowledgeBase
from natural_rag.baseline.routines import (
    apply_optimizations_inplace, extract_entries, routines_logger,  # extract_keywords, find_entries_by_keywords,
    find_similar_entries, get_random_excerpt, insert_entries_inplace,
    propose_optimizations, refine_entries, select_entries_of_interest, split_large_document
)
from natural_rag.baseline.utils import log_to_file
from natural_rag.data import Document

async def add_document_to_base(
    llm: LLM, base: TreeKnowledgeBase, doc: str, seed: int = 0, doc_header: str = ''
):
    # print(f'---------------- KEYWORDS ----------------')
    # keywords = await extract_keywords(llm, doc)
    # top_relevant_entry_names_from_keywords = find_entries_by_keywords(base, keywords)
    # excerpt = base.get_excerpt(top_relevant_entry_names_from_keywords)

    print(f'---------------- BUILDING ----------------')
    new_entries = await extract_entries(llm, doc, doc_header)
    top_relevant_entry_names = find_similar_entries(base, new_entries)

    if len(top_relevant_entry_names):
        print(f'---------------- REFINING ----------------')
        excerpt = base.get_excerpt(top_relevant_entry_names)
        entries_of_interest = await select_entries_of_interest(llm, new_entries, excerpt)
        new_entries = await refine_entries(llm, base, new_entries, excerpt, entries_of_interest)
    
    insert_entries_inplace(base, new_entries)

    print(f'---------------- OPTIMIZING ----------------')
    excerpt = get_random_excerpt(base, seed=seed, n_seed_entries=5, max_siblings=20)
    proposed_changes = await propose_optimizations(llm, base, excerpt)
    apply_optimizations_inplace(base, proposed_changes)


async def build_base_from_docs(
    llm: LLM, base: TreeKnowledgeBase, docs: list[Document], dump_stages_dir: Path
):
    dump_stages_dir.mkdir(exist_ok=True, parents=True)

    for doc_idx, doc in enumerate(docs):
        base_repr_file = dump_stages_dir / f'step_{doc_idx:04d}.txt'
        log_file = dump_stages_dir / f'step_{doc_idx:04d}.log'

        with log_to_file(routines_logger, log_file):
            print(f'Doc {doc_idx}: id={doc.id} title={doc.title}')

            if doc.text is None or len(doc.text) == 0:
                print('No text, skipping')
                continue

            if len(doc.text) > 4000:
                doc_parts = await split_large_document(llm, doc.text)
                for part_idx, (part_header, part) in enumerate(doc_parts):
                    print(f'Processing part {part_idx}/{len(doc_parts)}')
                    await add_document_to_base(llm, base, part, seed=doc_idx, doc_header=part_header)
            else:
                await add_document_to_base(llm, base, doc.text, seed=doc_idx)

            base_repr_file.write_text('\n'.join(base.get_excerpt().to_lines()))
