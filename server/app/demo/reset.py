"""Reset one owner-scoped Demo workspace and restore its fixture seed."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ..auth import conn
from ..settings import SETTINGS
from .bootstrap import bootstrap_owner


OWNER_TABLES = [
    "case_attachment_links",
    "case_attachment_documents",
    "case_interest_evidence",
    "profile_interests",
    "schedule_locks",
    "task_edge_evidence",
    "task_planning",
    "fact_validity",
    "fact_history",
    "analysis_review_versions",
    "import_case_sources",
    "schedule_drafts",
    "document_derivatives",
    "document_privacy_findings",
    "knowledge_evidence_sources",
    "knowledge_chunks",
    "knowledge_documents",
    "rule_semantics",
    "profile_versions",
    "source_documents",
    "evidence_lines",
    "document_lines",
    "documents",
    "review_events",
    "case_reviews",
    "vault_task_links",
    "vault_case_links",
    "task_material_links",
    "import_sources",
    "import_analysis_runs",
    "schedule_items",
    "task_edges",
    "analysis_metadata",
    "conflicts",
    "materials",
    "tasks",
    "rules",
    "evidence",
    "facts",
    "analysis_jobs",
    "imports",
    "import_batches",
    "vault_items",
    "account_settings",
    "sync_changes",
    "sync_operations",
    "cases",
    "demo_seed_state",
]


def _table_exists(connection, table: str) -> bool:
    return bool(
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
    )


def _delete_uploads(owner_id: str) -> None:
    root = SETTINGS.demo_upload_root.resolve()
    target = (root / owner_id).resolve()
    if target == root or root not in target.parents:
        raise RuntimeError("Refusing to delete outside DEMO_UPLOAD_ROOT")
    if target.exists():
        shutil.rmtree(target)
    from ..services.documents import document_root
    root=document_root();target=(root/owner_id).resolve()
    if target==root or root not in target.parents:
        raise RuntimeError('Refusing to delete outside Demo document root')
    if target.exists():
        shutil.rmtree(target)


def reset_owner(owner_id: str) -> dict[str, str | bool]:
    if not SETTINGS.demo_mode:
        raise RuntimeError("Demo reset requires DEMO_MODE=true")

    from ..main import database

    database()
    with conn() as connection:
        if not connection.execute("SELECT 1 FROM users WHERE id=?", (owner_id,)).fetchone():
            raise ValueError("Demo owner does not exist")
        for table in OWNER_TABLES:
            if _table_exists(connection, table):
                connection.execute(f"DELETE FROM {table} WHERE owner_id=?", (owner_id,))
    _delete_uploads(owner_id)
    return bootstrap_owner(owner_id)


def _owner_id(user: str) -> str:
    with conn() as connection:
        row = connection.execute(
            "SELECT id FROM users WHERE id=? OR lower(email)=lower(?)", (user, user)
        ).fetchone()
    if not row:
        raise ValueError("Demo user not found")
    return str(row["id"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset one RuleFlow Demo workspace")
    parser.add_argument("--user", required=True, help="Demo user id or email")
    args = parser.parse_args()
    if not SETTINGS.demo_mode:
        parser.error("Demo reset requires DEMO_MODE=true")
    from ..main import database
    database()
    owner_id = _owner_id(args.user)
    result = reset_owner(owner_id)
    print(f"reset owner={owner_id} fixture_version={result['fixture_version']}")


if __name__ == "__main__":
    main()
