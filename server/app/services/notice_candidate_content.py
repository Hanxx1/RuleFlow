"""RF-014 internal content experiment; no public DTO, provider or writes.

Aliases below exist only to reuse the single-notice validators. They are not
persisted EvidenceRef and must never be passed to Case/Review/Task execution.
The caller must first validate the candidate against an authorized snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal

from pydantic import ValidationError

from ..ai import AIAnalysis, AIInvalidOutput, validate_ai_payload, validate_candidates
from .date_candidates import extract_dates
from .notice_candidate_validation import CandidatePreview, CandidateValidationError


@dataclass(frozen=True)
class ContentSource:
    local_ref: str
    source_ref_index: int
    text: str


@dataclass(frozen=True)
class CandidateContentPreview:
    candidate_id: str
    sources: tuple[ContentSource, ...]
    # JSON snapshots keep nested lists/dicts immutable without changing AIAnalysis.
    analysis_json: str
    dates_json: str
    review_reasons: tuple[str, ...]
    eligibility: Literal['UNKNOWN'] = 'UNKNOWN'


def candidate_content_sources(candidate: CandidatePreview) -> tuple[ContentSource, ...]:
    """Expose candidate-local quotes, never the entire shared document.

    Include complete reference identity in the alias so another candidate or a
    changed quote/version cannot accidentally reuse an old content response.
    This digest is an internal binding, not authorization or a freshness check.
    """
    result = []
    for index, ref in enumerate(candidate.source_refs):
        identity = json.dumps([candidate.candidate_id, candidate.kind, candidate.title,
                               candidate.course_id, index, ref.model_dump()],
                              ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        digest = hashlib.sha256(identity.encode('utf-8')).hexdigest()
        result.append(ContentSource('block:rf014-' + digest, index, ref.quote))
    return tuple(result)


def _check_ast_bounds(ast: dict, refs: set[str]) -> None:
    # Bound traversal before the existing recursive validator; require grounded
    # leaves so a cited rule cannot hide an uncited second condition.
    pending = [(ast, 0)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if depth > 32 or count > 256 or not isinstance(node, dict):
            raise CandidateValidationError('CANDIDATE_CONTENT_AST_INVALID')
        evidence = node.get('evidence', [])
        if (not isinstance(evidence, list) or
                any(not isinstance(ref, str) or ref not in refs for ref in evidence)):
            raise CandidateValidationError('CANDIDATE_CONTENT_AST_INVALID')
        op = node.get('op')
        if not isinstance(op, str):
            raise CandidateValidationError('CANDIDATE_CONTENT_AST_INVALID')
        if op in {'and', 'or', 'not'}:
            children = node.get('args')
            if not isinstance(children, list) or not children or len(children) > 256:
                raise CandidateValidationError('CANDIDATE_CONTENT_AST_INVALID')
            pending.extend((child, depth + 1) for child in children)
        elif not evidence or not isinstance(node.get('field'), str):
            raise CandidateValidationError('CANDIDATE_CONTENT_AST_INVALID')


def validate_candidate_content(candidate: CandidatePreview, payload: object) -> CandidateContentPreview:
    """Strict read-only check of an AIAnalysis-shaped internal content draft.

    Reuses existing rule whitelist/type/semantic checks without evaluating a
    profile. Dates come from the program's existing extractor, remain candidates
    and are never assigned to a task automatically. No provider is called.
    """
    sources = candidate_content_sources(candidate)
    evidence = {source.local_ref: source.text for source in sources}
    try:
        analysis = AIAnalysis.model_validate(payload, strict=True).model_copy(deep=True)
    except ValidationError:
        raise CandidateValidationError('CANDIDATE_CONTENT_INVALID') from None
    items = [*analysis.rules, *analysis.materials, *analysis.tasks,
             *[item for item in (analysis.audience, analysis.submission,
                                *analysis.external_references, *analysis.unsupported_conditions)
               if item is not None]]
    for item in items:
        refs = item.evidence_ids
        if (not refs or len(refs) > 20 or len(set(refs)) != len(refs) or
                set(item.evidence_quotes) != set(refs)):
            raise CandidateValidationError('CANDIDATE_CONTENT_REFERENCE_INVALID')
        for ref, quote in item.evidence_quotes.items():
            if ref not in evidence or not quote.strip() or quote not in evidence[ref]:
                raise CandidateValidationError('CANDIDATE_CONTENT_REFERENCE_INVALID')
        label = getattr(item, 'title', getattr(item, 'label', None))
        if label is not None and not label.strip():
            raise CandidateValidationError('CANDIDATE_CONTENT_INVALID')
    for rule in analysis.rules:
        _check_ast_bounds(rule.ast, set(rule.evidence_ids))
    # The existing task schema permits a model deadline string. Do not accept it
    # here: the date extractor and a later explicit user decision own that step.
    if any(task.deadline is not None for task in analysis.tasks):
        raise CandidateValidationError('CANDIDATE_CONTENT_DEADLINE_UNCONFIRMED')
    try:
        analysis = validate_ai_payload(analysis.model_dump())
        reasons = set(validate_candidates(analysis, evidence))
    except AIInvalidOutput:
        raise CandidateValidationError('CANDIDATE_CONTENT_INVALID') from None
    reasons.update(candidate.review_reasons)
    reasons.add('USER_REVIEW_REQUIRED')
    if any(task.duration_minutes is not None for task in analysis.tasks):
        reasons.add('DURATION_REVIEW_REQUIRED')
    dates = extract_dates([(source.local_ref, source.text) for source in sources])
    if dates:
        reasons.add('DATE_REVIEW_REQUIRED')
    # No inferred qualification or execution state is accepted by AIAnalysis.
    try:
        analysis_json = json.dumps(analysis.model_dump(), ensure_ascii=False,
                                   sort_keys=True, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise CandidateValidationError('CANDIDATE_CONTENT_INVALID') from None
    return CandidateContentPreview(candidate.candidate_id, sources, analysis_json,
                                   json.dumps(dates, ensure_ascii=False, sort_keys=True, allow_nan=False),
                                   tuple(sorted(reasons)))
