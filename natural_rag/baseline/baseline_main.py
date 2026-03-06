from __future__ import annotations
import asyncio
from collections import defaultdict
from pathlib import Path
import pickle
from typing import cast
import os
from itertools import chain, islice

from diskcache import Index # pyright: ignore[reportMissingTypeStubs]
import numpy as np
import pandas as pd
from ragu.models.llm import LLMOpenAI # pyright: ignore[reportMissingTypeStubs]
from ragu.models.openai import CachedAsyncOpenAI # pyright: ignore[reportMissingTypeStubs]

from natural_rag.baseline import (
    CLARIFY_PROMPT, INSERT_PROMPT, BUILD_PROMPT, OPTIMIZE_PROMPT, Changes, EntriesList, Names, TreeKnowledgeBase
)


# from ragu.common.logger import logger # pyright: ignore[reportMissingTypeStubs]
# logger.remove()
# logger.add(sys.stdout, level="DEBUG") 

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

    for doc_idx, doc in enumerate(docs):
        print(f'Doc {doc_idx}: {doc.name}')
        doc = doc.read_text()
    
        print(f'----------------\nBUILDING\n----------------')
        
        new_entries = cast(EntriesList, await llm.chat_completion(
            [{"role": "user", "content": BUILD_PROMPT.format(document=doc)}],
            output_schema=EntriesList,
        )).entries
        print(f'Extracted {len(new_entries)} entries')
        # print(entries)

        found_relevant_entries: dict[str, float] = defaultdict(float)
        for entry in new_entries:
            for query in entry.get_all_fields():
                for score, name in base.search_entries(query, n=50):
                    found_relevant_entries[name] += score

        top_relevant_entries = sorted(
            found_relevant_entries.items(),
            key=lambda item: -item[1]
        )[:50]
        
        print(f'{top_relevant_entries=}')

        top_relevant_entry_names = [name for name, _score in top_relevant_entries]

        if len(top_relevant_entry_names):

            print(f'----------------\nCLARIFYING\n----------------')
            excerpt = base.get_excerpt(top_relevant_entry_names)
            excerpt_text = '\n'.join(excerpt.to_lines())
            # print('Excerpt from found entries:')
            # print(excerpt_text)

            names_to_clarify = cast(Names, await llm.chat_completion(
                [{"role": "user", "content": CLARIFY_PROMPT.format(
                    new_entries='\n'.join([e.model_dump_json() for e in new_entries]),
                    excerpt_tree=excerpt_text,
                )}],
                output_schema=Names,
            )).names
            print(f'{names_to_clarify=}')

            print(f'----------------\nREFINING\n----------------')
            refined_new_entries = cast(EntriesList, await llm.chat_completion(
                [{"role": "user", "content": INSERT_PROMPT.format(
                    new_entries='\n'.join([
                        e.model_dump_json()
                        for e in new_entries
                    ]),
                    excerpt_tree=excerpt_text,
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
                print(diff_df)

            new_entries = refined_new_entries
        
        print(f'----------------\nINSERTING\n----------------')

        for entry in new_entries:
            base.add_or_replace_entry(entry)
        
        base.check_if_entry_tree_valid()
    
        print(f'Inserted/modified entries: {[entry.name for entry in new_entries]}')

        print('All entries:')
        excerpt = base.get_excerpt()
        print('\n'.join(excerpt.to_lines()))

        print(f'----------------\nOPTIMIZING\n----------------')
        seed_entries = np.random.default_rng(0).choice(list(base._entries), 5) # pyright: ignore[reportPrivateUsage]
        print(f'Seed entries: {seed_entries}')
        seed_entries_with_parents = list(set([
            e.name for e in chain(*[base.get_full_path(e) for e in seed_entries])
        ]))
        all_entries_to_include = list(set(chain(*[
            islice(base.get_siblings(e), 20) for e in seed_entries_with_parents
        ])))
        excerpt = base.get_excerpt(all_entries_to_include)
        excerpt_text = '\n'.join(excerpt_lines := excerpt.to_lines())
        print(f'Total excerpt lines: {len(excerpt_lines)}')

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
            print(diff_df)
        
        for change in proposed_changes:
            if change.entry in base and (change.new_parent is None or change.new_parent in base):
                base.get_entry(change.entry).parent = change.new_parent

        # if doc_idx == 2:
        #     break

        Path(f'steps/step_{doc_idx:04d}.txt').write_text('\n'.join(base.get_excerpt().to_lines()))
    
    Path('bl30.pkl').write_bytes(pickle.dumps(base._entries)) # pyright: ignore[reportPrivateUsage]

if __name__ == '__main__':
    # base = TreeKnowledgeBase()
    # base.add_or_replace_entry(Entry(name='A', summary='xxxxx', text='', keywords=[], parent=None))
    # base.add_or_replace_entry(Entry(name='B', summary='xxxxx', text='', keywords=[], parent='A'))
    # base.add_or_replace_entry(Entry(name='B2', summary='xxxxx', text='', keywords=[], parent='A'))
    # base.add_or_replace_entry(Entry(name='C', summary='xxxxx', text='', keywords=[], parent='B'))
    # base.check_if_entry_tree_valid()
    # print('\n'.join(base.get_excerpt(['A', 'C']).to_lines()))
    asyncio.run(main())