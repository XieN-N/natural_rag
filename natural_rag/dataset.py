from __future__ import annotations
from pathlib import Path
import json
from typing import Self
import re

import yaml
from pydantic import BaseModel, Field, model_validator

from natural_rag.data import Question, Document


class RAGDataset(BaseModel):
    """A RAG corpus plus a set of questions.
    
    Can be saved to disk or loaded. On a disk, docs are represented as
    .md or .txt files, and questions are represented as .yaml files,
    to enable easy viewing and editing on disk.
    """
    
    documents: dict[str, Document] = Field(
        default_factory=dict,
        description=(
            'A mapping from document ID to a document.'
        )
    )
    
    questions: list[Question] = Field(
        default_factory=list[Question],
        description=(
            'A list of questions.'
        )
    )
    
    @model_validator(mode='after')
    def check_ids_exist(self) -> Self:
        for q in self.questions:
            if q.relevant is not None:
                for source in q.relevant:
                    assert source.doc_id in self.documents, (
                        f'doc ID {source.doc_id} mentioned as relevant'
                        ' for a question, but not in the documents'
                    )
        return self
    
    def __str__(self) -> str:
        report = [
            f'{len(self.documents)} documents',
            f'{len(self.questions)} questions',
        ]
        q_with_a = [q for q in self.questions if q.reference_answers]
        if len(q_with_a) < len(self.questions):
            report.append(f'{len(q_with_a)} questions with answers')
        return f'{self.__class__.__name__}({", ".join(report)})'
    
    __repr__ = __str__
    
    @classmethod
    def load_from_dir(
        cls,
        dir: str | Path,
        load_texts: bool = True,
        load_sources: bool = False,
        qa_path: str = 'questions.yaml',
        corpus_info_path: str = 'corpus_info.yaml',
        texts_dir: str = 'docs',
        sources_dir: str = 'sources',
    ) -> Self:
        """Loads from a dicectory organized as follows:
        
        - {dir}/corpus_info.yaml contains info about documents.
        - {dir}/questions.yaml contains questions (and optionally
          answers).
        - {dir}/docs/{id}.md (or .txt) contain documents
          (only the documents mentioned in corpus.yaml will be loaded).
          Will try to load .md, then .txt.
        - {dir}/sources/{id}{ext} optionally contain documents
          as sources, such as PDF or HTML (only the documents mentioned
          in corpus.yaml will be loaded). The extension is a field
          in the `Document` class.
          
        Such a structure enables easy viewing and editing on disk.
        
        By default, will load `Document` objects with `.text` and
        `.source` field filled, if the corresponding files exist. If the
        corpus is way too large, may skip loading texts with
        `load_texts=False`. May load sources with `load_sources=False`.
        """
        
        ROOT_DIR = Path(dir)
        
        qa_yaml_data = yaml.safe_load(
            (ROOT_DIR / qa_path).read_text()
        )
        assert isinstance(qa_yaml_data, list)
        qa = [
            Question.model_validate(entry)
            for entry in qa_yaml_data # pyright: ignore[reportUnknownVariableType]
        ]
        
        corpus_yaml_data = yaml.safe_load(
            (ROOT_DIR / corpus_info_path).read_text()
        )
        assert isinstance(corpus_yaml_data, list)
        docs = [
            Document.model_validate(entry)
            for entry in corpus_yaml_data # pyright: ignore[reportUnknownVariableType]
        ]
        
        if load_texts:
            for doc in docs:
                if (path := ROOT_DIR / texts_dir / f'{doc.id}.md').exists():
                    doc.text = path.read_text()
                elif (path := ROOT_DIR / texts_dir / f'{doc.id}.txt').exists():
                    doc.text = path.read_text()
        
        if load_sources:
            for doc in docs:
                rel_path = f'{doc.id}{doc.source_ext}'
                if (path := ROOT_DIR / sources_dir / rel_path).exists():
                    doc.source = path.read_bytes()
        
        return cls(
            documents={doc.id: doc for doc in docs},
            questions=qa,
        )

    @classmethod
    def load_multiq_chegeka_jsonl_from_dir(
        cls,
        dir: str | Path,
        load_sources: bool = False,
        docs_jsonl_path: str | None = None,
        questions_jsonl_path: str | None = None,
        sources_dir: str = 'sources',
    ) -> Self:
        """Loads multiq/chegeka-style datasets from JSONL files.

        Expected fields in questions JSONL:
        - `question` (required)
        - `answer` (optional)
        - `related_pages` (optional list of doc ids)
        - `metadata` (optional dict)
        - `id` (optional, saved in metadata)

        Expected fields in documents JSONL:
        - `id` (required)
        - `text` (optional)
        - `metadata` (optional dict)
        - `title` (optional, if missing may be read from metadata.title)
        """

        ROOT_DIR = Path(dir)

        def find_jsonl_file(explicit: str | None, prefix: str) -> Path:
            if explicit is not None:
                return ROOT_DIR / explicit
            candidates = sorted(ROOT_DIR.glob(f'{prefix}*.jsonl'))
            if len(candidates) == 1:
                return candidates[0]
            if (default_candidate := ROOT_DIR / f'{prefix}.jsonl').exists():
                return default_candidate
            raise FileNotFoundError(
                f'Could not uniquely resolve {prefix} JSONL in {ROOT_DIR}. '
                f'Found candidates: {[x.name for x in candidates]}'
            )

        def iter_jsonl(path: Path):
            for line_idx, line in enumerate(path.read_text().splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f'Invalid JSONL line in {path} at line {line_idx}'
                    ) from e
                if not isinstance(parsed, dict):
                    raise ValueError(
                        f'JSONL entry in {path} at line {line_idx} is not an object'
                    )
                yield parsed

        docs_path = find_jsonl_file(docs_jsonl_path, 'documents')
        questions_path = find_jsonl_file(questions_jsonl_path, 'questions')

        docs: list[Document] = []
        for raw_doc in iter_jsonl(docs_path):
            if 'id' not in raw_doc:
                raise ValueError(f'Document entry has no "id": {raw_doc}')
            raw_doc = dict(raw_doc)
            doc_id = str(raw_doc.pop('id'))
            text = raw_doc.pop('text', None)
            source_ext = str(raw_doc.pop('source_ext', ''))
            title = raw_doc.pop('title', None)
            metadata = raw_doc.pop('metadata', {})
            if metadata is None:
                metadata = {}
            if not isinstance(metadata, dict):
                raise ValueError(f'Document metadata must be an object for doc_id={doc_id}')
            if title is None and isinstance(metadata.get('title'), str):
                title = metadata['title']
            metadata = metadata | raw_doc
            docs.append(Document(
                id=doc_id,
                title=title,
                text=text,
                source_ext=source_ext,
                metadata=metadata,
            ))

        qa: list[Question] = []
        for raw_question in iter_jsonl(questions_path):
            raw_question = dict(raw_question)
            q_id = raw_question.pop('id', None)
            text = raw_question.pop('question', raw_question.pop('text', None))
            if text is None:
                raise ValueError(f'Question entry has no "question" / "text": {raw_question}')

            ref_answers = raw_question.pop('reference_answers', None)
            if ref_answers is None:
                answer = raw_question.pop('answer', None)
                if answer is None:
                    ref_answers = []
                else:
                    ref_answers = [str(answer)]
            elif isinstance(ref_answers, str):
                ref_answers = [ref_answers]
            else:
                ref_answers = [str(x) for x in ref_answers]

            related_pages = raw_question.pop('related_pages', None)
            relevant = (
                [{'doc_id': str(doc_id)} for doc_id in related_pages]
                if related_pages is not None
                else None
            )

            metadata = raw_question.pop('metadata', {})
            if metadata is None:
                metadata = {}
            if not isinstance(metadata, dict):
                raise ValueError(f'Question metadata must be an object for question id={q_id}')
            if q_id is not None:
                metadata = {'id': str(q_id)} | metadata
            metadata = metadata | raw_question

            qa.append(Question.model_validate({
                'text': text,
                'reference_answers': ref_answers,
                'relevant': relevant,
                'metadata': metadata,
            }))

        if load_sources:
            for doc in docs:
                rel_path = f'{doc.id}{doc.source_ext}'
                if (path := ROOT_DIR / sources_dir / rel_path).exists():
                    doc.source = path.read_bytes()

        return cls(
            documents={doc.id: doc for doc in docs},
            questions=qa,
        )
        
    
    def report_stats(self) -> str:
        report_lines: list[str] = []
        
        doc_sizes_ascending = sorted([
            (doc.id, len(doc.text))
            for doc in self.documents.values()
            if doc.text is not None
        ], key=lambda x: x[1])
        
        joint_text = '\n'.join([
            doc.text
            for doc in self.documents.values()
            if doc.text is not None
        ])
        
        report_lines.append(f'Total documents: {len(self.documents)}')
        report_lines.append(
            'Shortest documents in symbols:'
            f' {[size for _id, size in doc_sizes_ascending[:5]]}'
        )
        report_lines.append(
            'Longest documents in symbols:'
            f' {[size for _id, size in doc_sizes_ascending[::-1][:5]]}'
        )

        report_lines.append(f'Symbols: {len(joint_text)}')
        report_lines.append(f'Words: {len(re.findall(r'\w+', joint_text))}')
        report_lines.append(
            f'Pages (assuming 1800 chars/page): {len(joint_text) // 1800}'
        )
        
        report_lines.append(f'Total questions: {len(self.questions)}')
        report_lines.append(
            f'Total questions with answers:'
            f' {len([q for q in self.questions if q.reference_answers])}'
        )
        
        if len(self.questions):
            n_relevant_per_question = [
                len(q.relevant or []) for q in self.questions
            ]
            all_relevant_doc_ids: list[str] = sum([
                ([r.doc_id for r in (q.relevant or [])])
                for q in self.questions
            ], []) # type: ignore
            docs_without_questions = (
                {doc.id for doc in self.documents.values()}
                - set(all_relevant_doc_ids)
            )
            report_lines.append(
                'Min relevant docs per question:'
                f' {min(n_relevant_per_question)}'
            )
            report_lines.append(
                'Max relevant docs per question:'
                f' {max(n_relevant_per_question)}'
            )
            report_lines.append(
                'N docs without questions:'
                f' {len(docs_without_questions)}'
            )
        
        return '\n'.join(report_lines)
    
    def dump_to_dir(
        self,
        dir: str | Path,
        qa_path: str = 'questions.yaml',
        corpus_info_path: str = 'corpus_info.yaml',
        texts_dir: str = 'docs',
        sources_dir: str = 'sources',
    ):
        """Saves the dataset to the directory in the format described in
        `.load_from_dir()`.
        """
        
        ROOT_DIR = Path(dir)
        ROOT_DIR.mkdir(exist_ok=True, parents=True)
        
        documents_to_save: list[Document] = []
        for doc in self.documents.values():
            doc = doc.model_copy()
            if doc.text is not None:
                (ROOT_DIR / texts_dir).mkdir(exist_ok=True, parents=True)
                (ROOT_DIR / texts_dir / f'{doc.id}.md').write_text(doc.text)
                doc.text = None
            if doc.source is not None:
                rel_path = f'{doc.id}{doc.source_ext}'
                (ROOT_DIR / sources_dir).mkdir(exist_ok=True, parents=True)
                (ROOT_DIR / sources_dir / rel_path).write_bytes(doc.source)
                doc.text = None
            documents_to_save.append(doc)
        
        docs_as_dicts = [
            doc.model_dump(mode='json', exclude_defaults=True)
            for doc in documents_to_save
        ]
        (ROOT_DIR / corpus_info_path).write_text(
            yaml.dump(docs_as_dicts, sort_keys=False)
        )
        
        qa_as_dicts = [
            qa.model_dump(mode='json', exclude_defaults=True)
            for qa in self.questions
        ]
        (ROOT_DIR / qa_path).write_text(
            yaml.dump(qa_as_dicts, sort_keys=False)
        )
