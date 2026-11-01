"""Knowledge lookup providers with a strict Demo/Real boundary."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from ..settings import SETTINGS


ROOT = Path(__file__).resolve().parents[3]
DEMO_KNOWLEDGE_ROOT = ROOT / "shared" / "demo" / "knowledge"


class KnowledgeProvider(Protocol):
    def search(
        self,
        case: dict[str, Any],
        evidence: list[dict[str, Any]],
        rules: list[dict[str, Any]],
    ) -> dict[str, Any]: ...


class UnavailableKnowledgeProvider:
    def search(self, case, evidence, rules) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "items": [],
            "reason": "knowledge_provider_not_configured",
        }


class LocalKnowledgeProvider:
    def search(self,case,evidence,rules):
        from ..auth import conn
        from ..services.knowledge import search
        query='\n'.join([case.get('title','')]+[item.get('text','') for item in evidence])[:4000]
        with conn() as connection:return search(connection,case['owner_id'],query)


class DemoFixtureKnowledgeProvider:
    """Deterministic keyword matching over read-only, desensitized fixtures."""

    def __init__(self, root: Path = DEMO_KNOWLEDGE_ROOT):
        self.root = root.resolve()

    def _documents(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(self.root.glob("*.json"), key=lambda item: item.name)
        ]

    def search(self, case, evidence, rules) -> dict[str, Any]:
        corpus = "\n".join(
            [str(case.get("title", ""))]
            + [str(item.get("text", "")) for item in evidence]
            + [str(item.get("label", "")) for item in rules]
        ).casefold()
        items: list[dict[str, Any]] = []
        for document in self._documents():
            for section in document.get("sections", []):
                keywords = [str(item) for item in section.get("keywords", []) if item]
                matched = [keyword for keyword in keywords if keyword.casefold() in corpus]
                if not matched:
                    continue
                quote = str(section.get("text", ""))
                evidence_ids = sorted(
                    str(item["id"])
                    for item in evidence
                    if item.get("id")
                    and any(
                        keyword.casefold() in str(item.get("text", "")).casefold()
                        for keyword in matched
                    )
                )
                items.append(
                    {
                        "id": f"{document['document_id']}:{section['id']}",
                        "title": document["title"],
                        "publisher": document["publisher"],
                        "effective_date": document.get("effective_date"),
                        "matched_section": section["title"],
                        "quote": quote,
                        "url": document.get("url"),
                        "confidence": None,
                        "match_type": "fixture_keyword",
                        "match_score": round(len(matched) / max(len(keywords), 1), 3),
                        "evidence_ids": evidence_ids,
                        "reference": {
                            "document_id": document["document_id"],
                            "version": document["version"],
                            "locator": section["title"],
                            "section_id": section["id"],
                        },
                    }
                )
        items.sort(key=lambda item: (-item["match_score"], item["id"]))
        return {"status": "available", "items": items, "reason": None}


def get_knowledge_provider() -> KnowledgeProvider:
    if SETTINGS.demo_mode:
        return DemoFixtureKnowledgeProvider()
    return LocalKnowledgeProvider()
