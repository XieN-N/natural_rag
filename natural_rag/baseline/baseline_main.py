from __future__ import annotations
import asyncio
from pathlib import Path
import pickle
import sys
import os

from diskcache import Index # pyright: ignore[reportMissingTypeStubs]
from ragu.models.llm import LLMOpenAI # pyright: ignore[reportMissingTypeStubs]
from ragu.models.openai import CachedAsyncOpenAI # pyright: ignore[reportMissingTypeStubs]

from natural_rag.baseline.tree import TreeKnowledgeBase, Excerpt
from natural_rag.baseline.routines import (
    apply_optimizations_inplace, extract_entries,
    find_similar_entries, get_random_excerpt, insert_entries_inplace,
    propose_optimizations, refine_entries, select_entries_of_interest
)


from ragu.common.logger import logger # pyright: ignore[reportMissingTypeStubs]
logger.remove()
logger.add(sys.stdout, level="DEBUG") 


async def main():
    base = TreeKnowledgeBase()
    llm = LLMOpenAI(
        client=CachedAsyncOpenAI(
            base_url=os.environ['VSEGPT_BASE_URL'],
            api_key=os.environ['VSEGPT_KEY'],
            rate_min_delay=2,
            cache=Index('./llm_cache'),
        ),
        model_name='mistralai/mistral-medium-3',
    )

    docs = sorted(Path('datasets/bl_small/docs').glob('*.md'))
    docs += sorted(Path('datasets/bl/docs').glob('*.md'))[:20]

    for doc_idx, doc_path in enumerate(docs):
        print(f'Doc {doc_idx}: {doc_path.name}')
    
        print(f'---------------- BUILDING ----------------')
        new_entries = await extract_entries(llm, doc_path.read_text())
        top_relevant_entry_names = find_similar_entries(base, new_entries)

        if len(top_relevant_entry_names):
            print(f'---------------- REFINING ----------------')
            excerpt = base.get_excerpt(top_relevant_entry_names)
            entries_of_interest = await select_entries_of_interest(llm, new_entries, excerpt)
            new_entries = await refine_entries(llm, base, new_entries, excerpt, entries_of_interest)
        
        insert_entries_inplace(base, new_entries)

        print(f'---------------- OPTIMIZING ----------------')
        excerpt = get_random_excerpt(base, seed=doc_idx, n_seed_entries=5, max_siblings=20)
        proposed_changes = await propose_optimizations(llm, base, excerpt)
        apply_optimizations_inplace(base, proposed_changes)

        print('All entries:\n' + '\n'.join(base.get_excerpt().to_lines()))
        Path(f'steps/step_{doc_idx:04d}.txt').write_text('\n'.join(base.get_excerpt().to_lines()))
    
    Path('bl30.pkl').write_bytes(pickle.dumps(base._entries)) # pyright: ignore[reportPrivateUsage]

if __name__ == '__main__':
    asyncio.run(main())