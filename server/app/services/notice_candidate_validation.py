"""RF-014 internal preview experiment, not a public DTO or execution protocol.

The caller must supply a fresh snapshot from read_source_snapshot for the
authenticated owner and that same owner's allowed course IDs. This pure module
does not authorize resources, read storage, call a model or create business data.
Source references here are never EvidenceRef, and valid quotes do not establish
semantic correctness or eligibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..ai import AIUnavailable


class CandidateValidationError(ValueError):
    """Fixed content-free local errors; never forward model output in errors."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class _DraftModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)


class _SourceRef(_DraftModel):
    source_id: str = Field(min_length=1, max_length=200)
    content_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    document_id: str | None = Field(min_length=1, max_length=200)
    document_revision: int | None = Field(ge=1)
    line_id: str | None = Field(min_length=1, max_length=300)
    quote: str = Field(min_length=1, max_length=2000)

    @field_validator('source_id', 'quote')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('blank')
        return value


class _Candidate(_DraftModel):
    candidate_id: str = Field(min_length=1, max_length=200)
    kind: Literal['case', 'task', 'requirement', 'knowledge']
    title: str = Field(min_length=1, max_length=300)
    course_id: str | None = Field(min_length=1, max_length=200)
    source_refs: list[_SourceRef] = Field(min_length=1, max_length=20)

    @field_validator('candidate_id', 'title')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('blank')
        return value


class _Output(_DraftModel):
    batch_id: str = Field(min_length=1, max_length=200)
    batch_revision: int = Field(ge=0)
    candidates: list[_Candidate] = Field(max_length=20)


@dataclass(frozen=True)
class CandidatePreview:
    candidate_id: str
    kind: str
    title: str
    course_id: str | None
    source_refs: tuple[_SourceRef, ...]
    review_reasons: tuple[str, ...]
    eligibility: Literal['UNKNOWN'] = 'UNKNOWN'


def _reject(code):
    raise CandidateValidationError(code)


def _check_ref(ref, sources):
    source = sources.get(ref.source_id)
    if source is None:
        _reject('CANDIDATE_SOURCE_INVALID')
    if source.get('extraction', {}).get('state') != 'available':
        _reject('CANDIDATE_SOURCE_UNAVAILABLE')
    if ref.content_hash != source.get('content_hash'):
        _reject('CANDIDATE_SOURCE_STALE')
    reasons = set()
    if source.get('text_origin') == 'legacy_text':
        if any(value is not None for value in (ref.document_id, ref.document_revision, ref.line_id)):
            _reject('CANDIDATE_SOURCE_INVALID')
        text = source.get('text')
        reasons.add('SOURCE_LOCATION_UNAVAILABLE')
    elif source.get('text_origin') == 'document_lines':
        document = source.get('document_ref') or {}
        if ref.document_id != document.get('id') or not ref.document_id:
            _reject('CANDIDATE_SOURCE_INVALID')
        if ref.document_revision != document.get('revision'):
            _reject('CANDIDATE_SOURCE_STALE')
        matches = [line for line in source.get('lines', []) if line.get('line_id') == ref.line_id]
        if len(matches) != 1 or matches[0].get('document_id') != ref.document_id:
            _reject('CANDIDATE_SOURCE_INVALID')
        text = matches[0].get('text')
        if source.get('original', {}).get('state') != 'present':
            reasons.add('SOURCE_ORIGINAL_REVIEW_REQUIRED')
    else:
        _reject('CANDIDATE_SOURCE_INVALID')
    if not isinstance(text, str) or ref.quote not in text:
        _reject('CANDIDATE_QUOTE_INVALID')
    if source.get('parent_reference_state') == 'missing':
        reasons.add('SOURCE_PARENT_REVIEW_REQUIRED')
    return reasons


def validate_candidate_output(payload: object, snapshot: dict, *,
                              allowed_course_ids: frozenset[str] = frozenset()) -> tuple[CandidatePreview, ...]:
    """Validate an internal draft against an already authorized source snapshot.

    All-or-error: no partial preview is returned for an invalid item. The
    source hash and Document version are checked per reference because the
    existing batch revision alone does not identify all source changes.
    """
    try:
        output = _Output.model_validate(payload)
    except ValidationError:
        raise CandidateValidationError('CANDIDATE_OUTPUT_INVALID') from None
    if output.batch_id != snapshot.get('batch_id'):
        _reject('CANDIDATE_BATCH_INVALID')
    if output.batch_revision != snapshot.get('batch_revision'):
        _reject('CANDIDATE_BATCH_STALE')
    rows = snapshot.get('sources', [])
    sources = {source['source_id']: source for source in rows}
    if len(sources) != len(rows):
        _reject('CANDIDATE_SOURCE_INVALID')
    seen = set()
    result = []
    for candidate in output.candidates:
        if candidate.candidate_id in seen:
            _reject('CANDIDATE_ID_DUPLICATE')
        seen.add(candidate.candidate_id)
        if candidate.kind == 'case':
            if candidate.course_id is not None:
                _reject('CANDIDATE_TARGET_INVALID')
        elif not candidate.course_id or candidate.course_id not in allowed_course_ids:
            _reject('CANDIDATE_TARGET_INVALID')
        reasons = {'USER_REVIEW_REQUIRED'}
        refs = set()
        for ref in candidate.source_refs:
            key = (ref.source_id, ref.document_id, ref.document_revision, ref.line_id, ref.quote)
            if key in refs:
                _reject('CANDIDATE_REFERENCE_DUPLICATE')
            refs.add(key)
            reasons.update(_check_ref(ref, sources))
        result.append(CandidatePreview(candidate.candidate_id, candidate.kind, candidate.title,
                                       candidate.course_id, tuple(candidate.source_refs), tuple(sorted(reasons))))
    return tuple(result)


def preview_candidate_output(generate: Callable[[], object], snapshot: dict, *,
                             allowed_course_ids: frozenset[str] = frozenset()) -> tuple[CandidatePreview, ...]:
    """Preparation seam for Fake Provider tests; not wired to LLMProvider.

    Timeout/unconfigured providers produce an explicit safe error, never Demo
    data. Request authorization, timeouts and budgets remain the caller's job.
    """
    try:
        payload = generate()
    except (AIUnavailable, TimeoutError):
        raise CandidateValidationError('CANDIDATE_ANALYSIS_UNAVAILABLE') from None
    return validate_candidate_output(payload, snapshot, allowed_course_ids=allowed_course_ids)
