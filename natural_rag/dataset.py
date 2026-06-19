from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import json
from typing import Any, Self, Literal
import re

import yaml
from pydantic import BaseModel, Field, model_validator

from natural_rag.data import Question, Document, SourceLoc


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
            report.append(f'{len(q_with_a)} questions with answer_20')
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
          answer_20).
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
    def load_jsonl_from_dir(
        cls,
        dir: str | Path,
        load_sources: bool = False,
        sources_dir: str = 'sources',
    ) -> Self:
        """Loads dataset from JSONL files in the given folder.

        The directory must contain either:
        - one file matching `documents_*.jsonl` and one file matching
          `questions_*.jsonl`
        - `corpus.jsonl` and `questions.jsonl`
        """

        ROOT_DIR = Path(dir)

        def iter_jsonl(path: Path):
            for line_idx, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError as e:
                    snippet = line[:120].replace('\n', '\\n')
                    raise ValueError(
                        f'Invalid JSONL line in {path} at line {line_idx}: {snippet}'
                    ) from e
                if not isinstance(parsed, dict):
                    raise ValueError(
                        f'JSONL entry in {path} at line {line_idx} is not an object'
                    )
                yield parsed

        def merge_metadata_with_raw(
            metadata: dict,
            raw: dict,
        ) -> dict:
            # `raw` are top-level JSON fields; values from `metadata` override duplicates.
            return raw | metadata

        doc_candidates = sorted(ROOT_DIR.glob('documents_*.jsonl'))
        question_candidates = sorted(ROOT_DIR.glob('questions_*.jsonl'))
        if len(doc_candidates) == 1 and len(question_candidates) == 1:
            docs_path = doc_candidates[0]
            questions_path = question_candidates[0]
        elif (
            (ROOT_DIR / 'corpus.jsonl').exists()
            and (ROOT_DIR / 'questions.jsonl').exists()
        ):
            docs_path = ROOT_DIR / 'corpus.jsonl'
            questions_path = ROOT_DIR / 'questions.jsonl'
        else:
            raise FileNotFoundError(
                'Dataset directory must contain exactly one documents_*.jsonl '
                'and one questions_*.jsonl file, or corpus.jsonl and '
                f'questions.jsonl. Got docs={len(doc_candidates)}, '
                f'questions={len(question_candidates)} in {ROOT_DIR}'
            )

        docs: list[Document] = []
        for raw_doc in iter_jsonl(docs_path):
            raw_doc = dict(raw_doc)
            doc_id_raw = raw_doc.pop('id', None)
            if doc_id_raw is None:
                doc_id_raw = raw_doc.pop('doc_id', None)
            if doc_id_raw is None:
                raise ValueError(f'Document entry has no "id" / "doc_id": {raw_doc}')
            doc_id = str(doc_id_raw)
            text = raw_doc.pop('text', None)
            source_ext_raw = raw_doc.pop('source_ext', None)
            source_ext = '' if source_ext_raw is None else str(source_ext_raw)
            title = raw_doc.pop('title', None)
            metadata = raw_doc.pop('metadata', {})
            if metadata is None:
                metadata = {}
            if not isinstance(metadata, dict):
                raise ValueError(f'Document metadata must be an object for doc_id={doc_id}')
            if title is None and isinstance(metadata.get('title'), str):
                title = metadata['title']
            metadata = merge_metadata_with_raw(metadata=metadata, raw=raw_doc)
            docs.append(Document(
                id=doc_id,
                title=title,
                text=text,
                source_ext=source_ext,
                metadata=metadata,
            ))

        doc_ids = {doc.id for doc in docs}

        qa: list[Question] = []
        for raw_question in iter_jsonl(questions_path):
            raw_question = dict(raw_question)
            q_id = raw_question.pop('id', None)
            text = raw_question.pop('question', None)
            if text is None:
                raise ValueError(f'Question entry has no "question" / "text": {raw_question}')

            answer = raw_question.pop('answer', None)
            ref_answers = [str(answer)] if answer is not None else []

            related_pages = raw_question.pop('related_pages', None)
            relevant_source_field = 'related_pages'
            if related_pages is None:
                related_pages = raw_question.pop('gold_doc_ids', None)
                relevant_source_field = 'gold_doc_ids'
            if isinstance(related_pages, str):
                related_pages = [related_pages]
            if related_pages is not None:
                related_pages = [str(doc_id) for doc_id in related_pages]
                missing_relevant_doc_ids = [
                    doc_id for doc_id in related_pages if doc_id not in doc_ids
                ]
                relevant = [
                    SourceLoc(doc_id=doc_id, loc=None)
                    for doc_id in related_pages
                    if doc_id in doc_ids
                ]
            else:
                missing_relevant_doc_ids = []
                relevant = list()

            metadata = raw_question.pop('metadata', {})
            if metadata is None:
                metadata = {}
            if not isinstance(metadata, dict):
                q_id_for_err = '<missing>' if q_id is None else str(q_id)
                raise ValueError(
                    f'Question metadata must be an object for question id={q_id_for_err}'
                )
            metadata = merge_metadata_with_raw(metadata=metadata, raw=raw_question)
            if q_id is not None:
                metadata.setdefault('id', str(q_id))
            if related_pages is not None and relevant_source_field == 'gold_doc_ids':
                metadata.setdefault(relevant_source_field, related_pages)
            if missing_relevant_doc_ids:
                metadata.setdefault(
                    'missing_relevant_doc_ids',
                    missing_relevant_doc_ids,
                )

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

    @classmethod
    def load_2wikimultihopqa_json(
        cls,
        path: str | Path,
        max_examples: int | None = None,
    ) -> Self:
        """Loads the 2WikiMultihopQA JSON format as a natural_rag dataset.

        Each unique page title from an example's ``context`` becomes one
        document. If the same title appears in multiple examples, sentence
        lists are merged preserving first-seen order.
        """

        raw_data = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(raw_data, list):
            raise ValueError(f'2WikiMultihopQA file must contain a JSON list: {path}')
        if max_examples is not None:
            raw_data = raw_data[:max_examples]

        docs_by_id: dict[str, Document] = {}
        seen_sentences_by_doc: dict[str, set[str]] = defaultdict(set)
        questions: list[Question] = []

        for example_idx, raw_example in enumerate(raw_data):
            if not isinstance(raw_example, dict):
                raise ValueError(f'2WikiMultihopQA example #{example_idx} is not an object')

            question_text = raw_example.get('question')
            answer = raw_example.get('answer')
            context = raw_example.get('context')
            if not isinstance(question_text, str):
                raise ValueError(f'2WikiMultihopQA example #{example_idx} has no string question')
            if not isinstance(answer, str):
                raise ValueError(f'2WikiMultihopQA example #{example_idx} has no string answer')
            if not isinstance(context, list):
                raise ValueError(f'2WikiMultihopQA example #{example_idx} has no context list')

            context_sentences: dict[str, list[str]] = {}
            context_doc_ids: list[str] = []
            for page in context:
                if (
                    not isinstance(page, list)
                    or len(page) != 2
                    or not isinstance(page[0], str)
                    or not isinstance(page[1], list)
                ):
                    raise ValueError(
                        f'Invalid 2WikiMultihopQA context page in example #{example_idx}: {page!r}'
                    )

                title = page[0]
                sentences = [str(sentence) for sentence in page[1]]
                context_sentences[title] = sentences
                context_doc_ids.append(title)

                if title not in docs_by_id:
                    docs_by_id[title] = Document(
                        id=title,
                        title=title,
                        text='',
                        metadata={
                            'source_dataset': '2wikimultihopqa',
                            'source_example_ids': [],
                        },
                    )

                doc = docs_by_id[title]
                doc.metadata.setdefault('source_example_ids', [])
                source_example_ids = doc.metadata['source_example_ids']
                if isinstance(source_example_ids, list):
                    source_example_ids.append(str(raw_example.get('_id', example_idx)))

                merged_sentences: list[str] = []
                for sentence in sentences:
                    if sentence in seen_sentences_by_doc[title]:
                        continue
                    seen_sentences_by_doc[title].add(sentence)
                    merged_sentences.append(sentence)
                if merged_sentences:
                    existing_text = doc.text or ''
                    addition = '\n'.join(merged_sentences)
                    doc.text = f'{existing_text}\n{addition}'.strip()

            relevant_by_doc: dict[str, list[str]] = defaultdict(list)
            supporting_facts = raw_example.get('supporting_facts', [])
            if isinstance(supporting_facts, list):
                for fact in supporting_facts:
                    if (
                        not isinstance(fact, list)
                        or len(fact) != 2
                        or not isinstance(fact[0], str)
                    ):
                        continue
                    title = fact[0]
                    try:
                        sentence_idx = int(fact[1])
                    except (TypeError, ValueError):
                        continue
                    sentences = context_sentences.get(title, [])
                    if 0 <= sentence_idx < len(sentences):
                        relevant_by_doc[title].append(sentences[sentence_idx])
                    else:
                        relevant_by_doc[title].append(f'sentence:{sentence_idx}')

            metadata: dict[str, Any] = {
                'source_dataset': '2wikimultihopqa',
                'id': raw_example.get('_id'),
                'type': raw_example.get('type'),
                'context_doc_ids': context_doc_ids,
                'supporting_facts': raw_example.get('supporting_facts'),
                'evidences': raw_example.get('evidences'),
                'entity_ids': raw_example.get('entity_ids'),
                'evidences_id': raw_example.get('evidences_id'),
                'answer_id': raw_example.get('answer_id'),
            }
            questions.append(Question(
                text=question_text,
                reference_answers=[answer],
                relevant=[
                    SourceLoc(doc_id=doc_id, loc=locs)
                    for doc_id, locs in relevant_by_doc.items()
                    if doc_id in docs_by_id
                ],
                metadata=metadata,
            ))

        return cls(documents=docs_by_id, questions=questions)

    @classmethod
    def load_auto(
        cls,
        path: str | Path,
        **kwargs,
    ) -> Self:
        """Automatically detect dataset format and load accordingly.
        
        Supports:
        - YAML-based format (corpus_info.yaml + questions.yaml + docs/) -> load_from_dir
        - JSONL format (corpus.jsonl + questions.jsonl or documents_*.jsonl + questions_*.jsonl) -> load_jsonl_from_dir
        - 2WikiMultihopQA JSON format (single .json file) -> load_2wikimultihopqa_json
        """
        path = Path(path)
        
        if path.is_file():
            if path.suffix == '.json':
                return cls.load_2wikimultihopqa_json(path, **kwargs)
            raise ValueError(f'Unsupported file format: {path.suffix}')
        
        if path.is_dir():
            has_yaml = (path / 'corpus_info.yaml').exists() and (path / 'questions.yaml').exists()
            has_jsonl_corpus = (path / 'corpus.jsonl').exists() and (path / 'questions.jsonl').exists()
            has_jsonl_docs = len(list(path.glob('documents_*.jsonl'))) == 1 and len(list(path.glob('questions_*.jsonl'))) == 1
            
            if has_yaml:
                return cls.load_from_dir(path, **kwargs)
            elif has_jsonl_corpus or has_jsonl_docs:
                return cls.load_jsonl_from_dir(path, **kwargs)
            else:
                raise ValueError(
                    f'Directory {path} does not contain a recognized dataset format. '
                    'Expected either YAML format (corpus_info.yaml + questions.yaml) '
                    'or JSONL format (corpus.jsonl + questions.jsonl or documents_*.jsonl + questions_*.jsonl)'
                )
        
        raise ValueError(f'Path does not exist: {path}')

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
        word_count = len(re.findall(r"\w+", joint_text))
        report_lines.append(f"Words: {word_count}")
        report_lines.append(
            f'Pages (assuming 1800 chars/page): {len(joint_text) // 1800}'
        )
        
        report_lines.append(f'Total questions: {len(self.questions)}')
        report_lines.append(
            f'Total questions with answer_20:'
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
