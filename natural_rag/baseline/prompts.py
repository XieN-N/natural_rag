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

SPLITTING_PROMPT = f"""\
I have a potentially large document, and want to split it into self-sufficient smaller \
Documents. I will provide the document auto-splitted into sections, with additional \
marks like (Sec (i)). You need to group it into several smalled documents \
by indicating starting section index for each group. To give additional context, you \
should provide a header for each group which describes what was said earlier.

Each group should be around 3-4 pages of text. If there is no need to split, or splitting \
is impossible without breaking formatting, return `parts=None`.

The document:

{{document_with_marked_sections}}

<document end>\
"""

# KEYWORDS_PROMPT = f"""\
# I have a document, and want to query relevant documents in a large database. \
# I will provide the document, exctact keywords that may serve as search terms \
# for text or vector search. Provide main keywords and up to several dozens \
# additional keywords. For empty document return empty list.

# The document:

# {{document}}

# <document end>\
# """

BUILD_PROMPT = f"""\
Your task is to convert a plain text document into a structured knowledge base. \
{SCHEMA_DESCRIPTION}

Return only list[Entry] as json. Try to achieve full document coverage, prefer to \
cite the document text without changes. Parent may be another returned entry or none. \
Importantly: each entry should be at least a paragraph of text! Don't increase the \
number of entries unnecessarily; instead, supplement the entry descriptions.

Document metainfo (do not process): <metainfo>{{document_metainfo}}</metainfo>

The document:

{{document}}

<document end>\
"""

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