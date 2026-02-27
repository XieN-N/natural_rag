from __future__ import annotations
import asyncio
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, cast
import os

from diskcache import Index # pyright: ignore[reportMissingTypeStubs]
import pandas as pd
from pydantic import BaseModel
from ragu.models.llm import LLMOpenAI # pyright: ignore[reportMissingTypeStubs]
from ragu.models.openai import CachedAsyncOpenAI # pyright: ignore[reportMissingTypeStubs]

# from ragu.common.logger import logger # pyright: ignore[reportMissingTypeStubs]
# logger.remove()
# logger.add(sys.stdout, level="DEBUG") 

from natural_rag.vector_index import VectorIndex


class Entry(BaseModel):
    name: str
    summary: str
    text: str
    keywords: list[str]
    parent: str | None  # use None for root/unknown parent

    def model_post_init(self, __context: object):
        if self.parent == 'none':
            self.parent = None
    
    def get_all_fields(self) -> list[str]:
        return [self.name, self.summary, self.text] + self.keywords


class EntriesList(BaseModel):
    entries: list[Entry]


class Names(BaseModel):
    names: list[str]


# A database structure description included in various prompts

SCHEMA_DESCRIPTION = f"""\
The knowledge base consists of entries (name, summary, text, keywords, parent):

```
class Entry(BaseModel):
    name: str
    summary: str
    text: str
    keywords: list[str]
    parent: str | Literal['none']  # use none for root/unknown parent
```

**Entry** represents anything that can be described and titled: an entity, \
event, recipe, problem, story etc. Each entry has a globally unique name in \
the whole database. Entries will be organized as a tree, example:

- Napoleon Bonaparte
    - Napoleon's early life
        - Napoleon's mother
        - Napoleon at school
        ...
    - Napoleon plans an invasion of Russia
    - Napoleon's exile to Elba
    - Cultural depictions of Napoleon
        - Ethical debates around Napoleon
        - Napoleon in the British press
        - ...

**Text** of each entry typically contains one paragraph of text. If \
there is more to say, it should be split into a tree of entries, as \
in the example. Texts may partially duplicate each other, and in \
total should completely cover all documents. Importantly, text may contain \
references to another entries in markdown format. Example:

"The Big Iron Shrek":
  keywords:
    - mechanical monster
    - boss
    - giant
  summary: A boss-like creature in the Swamp biome.
  text: >-
    A large neutral creature.
    Spawns uncommonly in the [Swamp](Swamp biome).
    Sometimes spawns on the [Big Donkey](Big Donkey).
    Has the [War Stomp](War Stomp) ability.
  parent: Swamp biome

The `text` field **should** mention all entry names which are children
of the current entry.

The goal of the hierarchical knowladge base is to efficiently search for relevant \
information for question answering system. To this end, **summary** should \
provide a one-sentence description of what is said in the **text**, to glance \
quickly through the list of summaries. **Keywords** is a list of words of \
phrases to perform semantic search.\
"""

# For BUILD_PROMPT output_schema is EntriesList

BUILD_PROMPT = f"""\
Your task is to convert a plain text document into a structured knowledge base. \
{SCHEMA_DESCRIPTION}

Return only list[Entry] as json. Try to achieve full document coverage, prefer to \
cite the document text without changes. Parent may be another returned entry or none.

The document:

{{document}}

<document end>\
"""

# For CLARIFY_PROMPT output_schema is Names

CLARIFY_PROMPT = f"""\
I am building a structured knowledge base. {SCHEMA_DESCRIPTION}

Currently, I am doing a **step** to supplement the base. I have a list of new \
entries extracted from a new document. These entries potentially can duplicate \
entries already present in the database. So, I need to merge current database with \
the new data.

Below, I first provide the new entries. Then I provide the excerpt from the database \
in form of tree, with entry names and summaries.

First, tell me a **list of entry names in the excerpt** for which you want to get \
full texts. Either they are candidates for duplicates, or they are needed to clarify \
the hierarchy, to understand where to append new entries.

New entries:

{{new_entries}}

The database excerpt:

{{excerpt_tree}}

So, now tell me a list of entry names in the excerpt to study in more details, \
possibly empty.\
"""

# For INSERT_PROMPT output_schema is EntriesList

INSERT_PROMPT = f"""\
I am building a structured knowledge base. {SCHEMA_DESCRIPTION}

Currently, I am doing a **step** to supplement the base. I have a list of new \
entries extracted from a new document. These entries potentially can duplicate \
entries already present in the database. So, I need to merge current database with \
the new data.

Below, I first provide the new entries. Then I provide the excerpt from the database \
in form of tree, with entry names and summaries. Finally, I provide full texts for
some entries from insert, possibly relevant or not.

New entries:

{{new_entries}}

The database excerpt:

{{excerpt_tree}}

Some full entries from the excerpt:

{{excerpt_entries}}

You need to **merge the new entries into the database**. Return a final list of \
entries to add or modify. If you observe double inheritance, that is, node X
is a child of on P1 and P2 in old and new versions, remove the least direct
inheritance.

Typically, you need to return all the new entries, possibly **correcting the \
parent** and omitting `text` field to save response size, if you don't have a \
reason to correct the text.

Also, you can **merge** the new entry and the entry from excerpt, if they are \
duplicate. To do so, return the entry with the name from excerpt, and the merged \
text.\
"""


class TreeKnowledgeBase:
    """Keeps a list of entries and a vector search engine.

    When a new entry is added, all its fields are added to the
    vector search engine as keys (typically embedded into vectors),
    and the entry name is added as a value for all these keys.

    Thus, you can find an entry either via its keywords, or
    its name, summary, or full text.
    """

    def __init__(self) -> None:
        self._entries: dict[str, Entry] = {}
        self._vector_index = VectorIndex()
    
    def get_entry(self, name: str) -> Entry:
        return self._entries[name]
    
    def __contains__(self, item: str):
        return item in self._entries

    def search_entries(self, query: str, n: int = 50) -> list[tuple[float, str]]:
        """Runs a vector search engine.
        
        Returns names of the top N records similar to query,
        and their similarity scores.
        """
        return self._vector_index.search(query, n)
    
    def add_or_replace_entry(self, entry: Entry):
        """Adds a new entry or replaces an existing entry.
        
        Updates the vector index accordingly.
        """
        if entry.name in self._entries:
            self.remove_entry(entry.name)
        self._entries[entry.name] = entry
        
        self._vector_index.add(entry.name, entry.get_all_fields())

    def remove_entry(self, name: str):
        """Removes the entry by name.
        
        Updates the vector index accordingly.
        """
        del self._entries[name]
        self._vector_index.remove(name)
    
    def check_if_entry_tree_valid(self):
        # self.as_tree()
        for entry in self._entries.values():
            chain = [entry.name]
            while entry.parent:
                parent = self._entries.get(entry.parent, None)
                assert parent, (
                    'Entry tree is invalid:'
                    f' parent {entry.parent} of {entry.name} is not present'
                )
                assert parent.name not in chain, (
                    'Entry tree is invalid:'
                    f' circular denendency of {chain + [parent.name]}'
                )
                chain.append(parent.name)
                entry = parent

    # def as_tree(self) -> tuple[TreeNode, dict[str, TreeNode]]:
    #     root = TreeNode('root')
    #     nodes = {name: TreeNode(entry) for name, entry in self._entries.items()}
    #     for node in nodes.values():
    #         entry = cast(Entry, node.value)
    #         try:
    #             node.parent = nodes[entry.parent] if (entry.parent is not None) else root
    #         except IndexError:
    #             raise ValueError(f'Cannot find parent {entry.parent} for entry {entry.name}')
    #     return root, nodes
    
    # def get_tree_excerpt(self, names: list[str]) -> TreeNode:
    #     root, all_nodes = self.as_tree()
    #     keep_entries = {name: all_nodes[name] for name in names}
    #     keep_entries |= {
    #         parent.value.name: parent
    #         for node in keep_entries.values()
    #         for parent in node.ancestors
    #         if isinstance(parent.value, Entry)
    #     }
    #     for child in root.descendants:
    #         if (
    #             isinstance(child.value, Entry)
    #             and child.value.name not in keep_entries
    #         ):
    #             child.parent.n_omitted += 1 # type: ignore
    #             child.parent = None # type: ignore
    #     return root

    def get_excerpt(self, names: list[str] | None = None) -> Excerpt:
        excerpt = Excerpt('root', {})

        def get_full_path(name: str) -> Iterable[Entry]:
            entry = self._entries[name]
            yield entry
            while entry.parent:
                entry = self._entries[entry.parent]
                yield entry
        
        def add_chain_inplace(chain: list[Entry], excerpt: Excerpt):
            while chain:
                entry = chain.pop(0)
                if entry.name not in excerpt.children:
                    excerpt.children[entry.name] = Excerpt(entry, {})
                excerpt = excerpt.children[entry.name]
        
        for name in (names if names is not None else list(self._entries)):
            chain = list(get_full_path(name))[::-1]
            add_chain_inplace(chain, excerpt)
        
        def count_omitted_inplace(excerpt: Excerpt):
            current_name = excerpt.value.name if excerpt.value != 'root' else None
            excerpt.n_omitted = len([
                entry for entry in self._entries.values()
                if entry.parent == current_name
                and entry.name not in excerpt.children
            ])
            for child in excerpt.children.values():
                count_omitted_inplace(child)
            
        count_omitted_inplace(excerpt)

        return excerpt

# @dataclass
# class OmittedNodes:
#     n: int

#     def to_string(self) -> str:
#         return f'\t({self.n} more child entries not shown)'

# @dataclass
# class TreeNode(Node):
#     value: Entry | Literal['root'] | OmittedNodes
#     n_omitted: int = 0

#     def __post_init__(self):
#         match self.value:
#             case Entry():
#                 name = self.value.name
#             case 'root':
#                 name = 'root'
#             case OmittedNodes():
#                 name = self.value.to_string()
#         super().__init__(name)

@dataclass
class Excerpt:
    value: Entry | Literal['root']
    children: dict[str, Excerpt]
    n_omitted: int = -1

    def to_lines(self) -> list[str]:
        result: list[str] = []
        if self.value != 'root':
            result.append(f'{self.value.name}: {self.value.summary}')
        else:
            result.append('<root>')
        if self.n_omitted > 0:
            result.append(f'├── ({self.n_omitted} more child entries not shown)')
        for child_idx, child in enumerate(self.children.values()):
            for child_line_idx, line in enumerate(child.to_lines()):
                if child_idx == len(self.children) - 1:
                    if child_line_idx == 0:
                        tab = '└── '
                    else:
                        tab = '    '
                else:
                    if child_line_idx == 0:
                        tab = '├── '
                    else:
                        tab = '│   '
                result.append(tab + line)
        return result


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
    # docs += [
    #     Path('datasets/bl/docs/Alembic.md'),
    #     Path('datasets/bl/docs/Anadia.md'),
    #     Path('datasets/bl/docs/Chiromaw.md'),
    # ]

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
            print('Excerpt from found entries:')
            print(excerpt_text)

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
    
        excerpt = base.get_excerpt()
        print('\n'.join(excerpt.to_lines()))

        # if doc_idx == 2:
        #     break

if __name__ == '__main__':
    # base = TreeKnowledgeBase()
    # base.add_or_replace_entry(Entry(name='A', summary='xxxxx', text='', keywords=[], parent=None))
    # base.add_or_replace_entry(Entry(name='B', summary='xxxxx', text='', keywords=[], parent='A'))
    # base.add_or_replace_entry(Entry(name='B2', summary='xxxxx', text='', keywords=[], parent='A'))
    # base.add_or_replace_entry(Entry(name='C', summary='xxxxx', text='', keywords=[], parent='B'))
    # base.check_if_entry_tree_valid()
    # print('\n'.join(base.get_excerpt(['A', 'C']).to_lines()))
    asyncio.run(main())