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


# class Keywords(BaseModel):
#     main: list[str] = Field(description="Most important keywords or phrases for the document.")
#     additional: list[str] = Field(description="Additional keywords or phrases for the document.")