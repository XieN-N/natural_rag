from __future__ import annotations

from pydantic import BaseModel, Field


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


class SplitDocument(BaseModel):
    """A set of separators to split a large document, and additional comments
    before each part to give context.
    
    For small documents `parts` is None. Otherwise the first part should have
    `starting_section_id = 0`, and then `starting_section_id` grows monotonically.
    """

    parts: list[SplitDocumentPart] | None = None


class SplitDocumentPart(BaseModel):
    """A single part of a large split document."""

    starting_section_id: int = Field(description=(
        "Index of the first section. The last section can be determined"
        " automatically from the start section of the next part."
    ))

    header: str = Field(default="", description=(
        'An additional header paragraph that is not present in the original docment, but should'
        ' be added to the split version to give the context. In the first part, header'
        ' typically should say that "This is the trimmed version of the document".'
        ' In the subsequent parts, header should give the understanding of the context, like'
        ' "This is a continuation of the document that talked about...". Do not use markdown'
        ' or line breaks in header.'
    ))


# class Keywords(BaseModel):
#     main: list[str] = Field(description="Most important keywords or phrases for the document.")
#     additional: list[str] = Field(description="Additional keywords or phrases for the document.")