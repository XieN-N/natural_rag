from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Literal

from pydantic import BaseModel, Field

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


class Change(BaseModel):
    entry: str
    new_parent: str | None = Field(description="New parent entry name, use None for root.")

    def model_post_init(self, __context: object):
        if self.new_parent in ('none', '<root>', 'root'):
            self.new_parent = None


class Changes(BaseModel):
    changes: list[Change]


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
cite the document text without changes. Parent may be another returned entry or none. \
Importantly: each entry should be at least a paragraph of text! Don't increase the \
number of entries unnecessarily; instead, supplement the entry descriptions.

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

# For database optimizing

OPTIMIZE_PROMPT = f"""\
I am building a structured knowledge base. {SCHEMA_DESCRIPTION}

I need to optimize structure of the existing knowledge base. Check for \
inconsisitencies in the database structure below. Propose parent changes \
for entries where you feel that the entry is more related to the new parent, \
than to the current parent. Propose changes if you are sure, otherwise return \
nothing if structure is fine. \

{{excerpt_tree}}

Now tell me which parent changes you propose.
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

    def get_full_path(self, name: str) -> Iterable[Entry]:
        entry = self._entries[name]
        yield entry
        while entry.parent:
            entry = self._entries[entry.parent]
            yield entry
    
    def get_siblings(self, name: str) -> Iterable[str]:
        parent = self._entries[name].parent
        for name, entry in self._entries.items():
            if entry.parent == parent:
                yield name

    def get_excerpt(self, names: list[str] | None = None) -> Excerpt:
        excerpt = Excerpt('root', {})
        
        def add_chain_inplace(chain: list[Entry], excerpt: Excerpt):
            while chain:
                entry = chain.pop(0)
                if entry.name not in excerpt.children:
                    excerpt.children[entry.name] = Excerpt(entry, {})
                excerpt = excerpt.children[entry.name]
        
        for name in (names if names is not None else list(self._entries)):
            chain = list(self.get_full_path(name))[::-1]
            add_chain_inplace(chain, excerpt)
        
        def count_omitted_inplace(excerpt: Excerpt):
            current_name = excerpt.value.name if excerpt.value != 'root' else None
            excerpt.n_omitted = len([
                entry for entry in self._entries.values()
                if entry.parent == current_name
                and entry.name not in excerpt.children
            ]) if excerpt.children else 0
            for child in excerpt.children.values():
                count_omitted_inplace(child)
            
        count_omitted_inplace(excerpt)

        return excerpt

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
            tab = '├── ' if self.children else '└── '
            result.append(f'{tab}({self.n_omitted} more child entries not shown)')
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


# from collections.abc import Iterable
# from itertools import chain
# import random
# from bigtree.node.node import Node
# from bigtree.tree.export import print_tree

# def get_excerpt(
#     root: Node,
#     select: Iterable[Node] | int,
#     expand_siblings: bool = False,
#     n_omitted_siblings: bool = True,
#     n_omitted_children: bool = True,
# ) -> Node:
#     if isinstance(select, int):
#         all_descendants = list(root.descendants)
#         select = random.sample(all_descendants, min(select, len(all_descendants)))
#     select = set(select)
#     if expand_siblings:
#         select |= set(chain(*[node.siblings for node in select]))
#     subtree = set(chain(*[node.node_path for node in select]))
            
#     def build_pruned_tree(orig_node: Node) -> Node:
#         new_node = Node(orig_node.name)
#         for child in orig_node.children:
#             if child in subtree:
#                 build_pruned_tree(child).parent = new_node
#         if len(new_node.children) == 0:
#             if n_omitted_children:
#                 n_children = len(list(orig_node.descendants))
#                 if n_children:
#                     new_node.name += f' ({n_children} children omitted)'
#         elif n_omitted_siblings:
#                 n_omitted = len(orig_node.children) - len(new_node.children)
#                 if n_omitted:
#                     Node(f"({n_omitted} more nodes omitted)", parent=new_node)
#         return new_node

#     return build_pruned_tree(root)

# root = Node("Root")
# for i in list("ABCDEFGHIJ"):
#     child = Node(f"Node_{i}", parent=root)
#     for j in range(1, 7):
#         Node(f"Node_{i}{j}", parent=child)

# print_tree(get_excerpt(root, select=3, expand_siblings=True))