from __future__ import annotations
from typing import Any, Literal

from pydantic import BaseModel, Field


class Document(BaseModel):
    """A document in a RAG corpus."""

    id: str = Field(description=(
        'A unique string identifier for a document. If all the documents have'
        ' unique titles, `id` can be equal to the `.title`. Should be a valid'
        ' filepath without extension (that is, may contain slash "/"'
        ' characters).'
    ))

    title: str | None = Field(default=None, description=(
        'A document title, may be None if document is untitled.'
    ))

    text: str | None = Field(default=None, description=(
        'A full text. May be omitted if, for example, no pre-defined PDF'
        ' parsing is given for the dataset. For documents with images, one can'
        ' subclass `Document` with additional fields.'
    ))

    source: bytes | None = Field(default=None, description=(
        'A source in the original format. For example, PDF bytes or HTML. May'
        ' be omitted, typically in cases when the `text` is given.'
    ))
    
    source_ext: str = Field(default='', description=(
        'An extension for the `.source` as file, starting from dot, if'
        ' specified.'
    ))

    metadata: dict[str, Any] = Field(default_factory=dict, description=(
        'Any additional metadata.'
    ))


class SourceLoc(BaseModel):
    """A location of relevant information in a corpus. If the relevant
    information is scattered across muitple documents, it can be
    represented as a list of `SourceLoc`.
    """
    
    doc_id: str = Field(description=(
        'A unique string identifier for a document.'
    ))
    
    loc: list[tuple[int, int] | str] | None = Field(
        default=None,
        description=(
            'A list of relevant spans. A relevans span is represented either'
            ' as start and end positions in characters, or as a start'
            ' substring (until end of sentence), or as a heading for a section'
            ' in markdown (should be enclosed here in [brackets]).'
        )
    )


class Question(BaseModel):
    """A question for a RAG corpus, supplemented with data to evaluate
    responses (such as the reference answer).
    """

    text: str = Field(description=(
        'A question text.'
    ))
    
    reference_answers: list[str] = Field(
        default_factory=list[str],
        description=(
            'A ground truth answer, if provided. May be more than one.'
        ),
    )
    
    eval_rules: LLMJudgeEvalChecklist | None = Field(
        default=None,
        description=(
            'One or more checks if the question supports fine-grained evaluation.'
        )
    )
    
    relevant: list[SourceLoc] | None = Field(default=None, description=(
        'Locations of the relevant information in the corpus, if provided.'
    ))
  
    metadata: dict[str, Any] = Field(default_factory=dict, description=(
        'Any additional metadata. For example, may have "tags" field with a'
        ' list of tags for the question. May also contain "comment" field'
        ' which is an optional commentary about the question. The comment may'
        ' explain why the qustion have some tag, or why it lacks the ground'
        ' truch answer etc. Is for practioners to read. By default is also'
        ' used by LLM-as-judge.'
    ))


class LLMJudgeEvalChecklist(BaseModel):
    """A list of `LLMJudgeEvalCheck` if the question supports
    fine-grained evaluation based on a set of rules. The LLM judge
    evaluates the answer according to each of the rules.
    """

    checks: dict[str, LLMJudgeEvalCheck] = Field(default_factory=dict, description=(
        'Checks and their identifiers that are unique within the question.'
    ))


class LLMJudgeEvalCheck(BaseModel):
    """A single rule for LLM judge to evaluate the answer granularly."""

    score: int = Field(description=(
        'A score given if the `check` is passed. May pe positive if the check'
        ' represents a good answer, negative if the check represents something'
        ' wrong that should not be mentioned, or zero if the check represents'
        ' some additional info in the answer, that is not required.'
    ))
    
    check: str = Field(description=(
        'An instruction for LLM-as-judge, typically in form of "mention'
        ' <something> in the answer". Should be unambiguous, so that the LLM'
        ' judge can easily tell "yes" or "no": is the check passed or not.'
    ))
  
    metadata: dict[str, Any] = Field(default_factory=dict, description=(
        'Any additional metadata. May contain "comment" field in the same way'
        ' as the `Question` may contain it. By default is also used by'
        ' LLM-as-judge.'
    ))



# classes for LLM judge response:


class ChecklistEvaluated(BaseModel):
    """Evaluated LLMJudgeEvalChecklist."""

    checks: dict[str, CheckEvaluated] = Field(default_factory=dict, description=(
        'Identifiers and evaluations for each check.'
    ))

class CheckEvaluated(BaseModel):
    """Evaluated LLMJudgeEvalCheck."""

    reasoning: str = Field(description=(
        'One or two sentences to justify your decision.'
    ))

    confidence: Literal['low', 'moderate', 'high'] = Field(description=(
        'Lower your confidence if you are not sure, or the check is ambiguous.'
    ))

    decision: bool = Field(description=(
        'Is this check true for the given answer? Yes or no.'
    ))