"""RF-051 operator CLI and isolated business readback, using temporary synthetic accounts."""
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from app import auth
from app.bootstrap import database
from app.providers import vault
from helpers import account, client, confirm_import, head

CLI = Path(__file__).resolve().parents[2] / "scripts" / "server-data-backup.py"


def invoke(*args, failure=None):
    result = subprocess.run([sys.executable, "-B", CLI, *args], capture_output=True,
                            text=True, timeout=45)
    if failure:
        assert result.returncode == 1
        assert result.stderr.strip() == f"{args[0]} FAILED {failure}"
        assert not result.stdout
    else:
        assert result.returncode == 0, result.stderr
    return result.stdout


def backup(source, target, *options, failure=None):
    return invoke("backup", "--writers-stopped", "--data-dir", source, "--output", target,
                  *options, failure=failure)


@pytest.fixture
def source(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    monkeypatch.setattr(auth, "DB", root / "ruleflow.db")
    database()
    return root


def configure_roots(monkeypatch, documents, uploads):
    monkeypatch.setenv("DOCUMENT_UPLOAD_ROOT", str(documents))
    monkeypatch.setattr(vault, "SETTINGS", replace(vault.SETTINGS, vault_upload_root=uploads))


def test_restored_accounts_originals_evidence_and_task_link(source, tmp_path, monkeypatch):
    documents = tmp_path / "custom-documents"
    configure_roots(monkeypatch, documents, source / "vault_uploads")
    owner, other = account("backup-a@example.com"), account("backup-b@example.com")
    headers = head(owner)
    raw = "请填写申请表。\n请提交实验报告。".encode()
    imported, = client.post("/api/v1/imports/files", headers=headers, data={"consent": "true"},
                            files={"files": ("notice.txt", raw, "text/plain")}).json()["data"]
    document = "/api/v1/documents/" + imported["document_id"]
    resources = "/api/v1/cases/" + imported["case_id"] + "/resources"
    evidence = client.get(resources, headers=headers).json()["data"]["evidence"]
    assert len({row["line_id"] for row in evidence}) == 2
    confirm_import(owner, imported["case_id"])
    task = client.post("/api/v1/cases/" + imported["case_id"] + "/tasks", headers=headers,
                       json={"title": "提交材料", "evidence_ids": [evidence[0]["id"]]}).json()["data"]
    content = b"Synthetic Vault bytes"
    item = client.post("/api/v1/vault/items", headers=headers,
                       data={"consent": "true", "case_ids": json.dumps([imported["case_id"]]),
                             "task_ids": json.dumps([task["id"]])},
                       files={"file": ("sample.txt", content, "text/plain")}).json()["data"]
    monkeypatch.setattr("app.main.parse_bytes", lambda *args: [])
    failed, = client.post("/api/v1/imports/files", headers=headers, data={"consent": "true"},
                          files={"files": ("unparsed.txt", b"Unparsed", "text/plain")}).json()["data"]
    assert failed["error_code"] == "OCR_EMPTY"
    bundle, restored = tmp_path / "backup", tmp_path / "restored"
    assert "documents=2 vault=1" in backup(source, bundle, "--document-root", documents)
    invoke("verify", "--backup", bundle)
    invoke("restore", "--backup", bundle, "--output", restored)

    # Physically take originals offline; an unnoticed fallback cannot satisfy the assertions.
    gc.collect()  # Release idle sqlite connection cycles before Windows directory rename.
    source.rename(tmp_path / "source-offline")
    documents.rename(tmp_path / "documents-offline")
    monkeypatch.setattr(auth, "DB", restored / "ruleflow.db")
    configure_roots(monkeypatch, restored / "document_uploads", restored / "vault_uploads")
    urls = {document + "/content": raw, item["content_url"]: content,
            "/api/v1/documents/" + failed["document_id"] + "/content": b"Unparsed"}
    for url, expected in urls.items():
        response = client.get(url, headers=headers)
        assert response.status_code == 200 and response.content == expected
        assert client.get(url, headers=head(other)).status_code == 404
    assert client.get(resources, headers=headers).json()["data"]["evidence"] == evidence
    assert client.get(resources, headers=head(other)).status_code == 404
    items = client.get("/api/v1/vault/items", params={"task_id": task["id"]},
                       headers=headers).json()["data"]
    assert [row["id"] for row in items] == [item["id"]]


def test_committed_wal_and_empty_roots(source, tmp_path):
    # Hold an idle connection so committed pages remain in WAL throughout the backup.
    with closing(sqlite3.connect(source / "ruleflow.db")) as db:
        db.execute("PRAGMA wal_autocheckpoint=0")
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db.execute("CREATE TABLE rf051_wal_example(value TEXT)")
        db.execute("INSERT INTO rf051_wal_example VALUES ('committed')")
        db.commit()
        assert (source / "ruleflow.db-wal").stat().st_size > 32
        (source / ".env").write_text("synthetic-placeholder")
        bundle = tmp_path / "backup"
        assert "documents=0 vault=0" in backup(source, bundle)
        assert {p.name for p in bundle.iterdir()} == {
            "ruleflow.db", "manifest.json", "document_uploads", "vault_uploads"}
        invoke("verify", "--backup", bundle)
        with closing(sqlite3.connect(bundle / "ruleflow.db")) as snapshot:
            assert snapshot.execute("SELECT * FROM rf051_wal_example").fetchall() == [("committed",)]


def test_missing_or_modified_original_before_backup(source, tmp_path, monkeypatch):
    docs = source / "document_uploads"
    configure_roots(monkeypatch, docs, source / "vault_uploads")
    user = account("missing-doc@example.com")
    raw = b"Source bytes"
    row, = client.post("/api/v1/imports/files", headers=head(user), data={"consent": "true"},
                       files={"files": ("sample.txt", raw, "text/plain")}).json()["data"]
    file = docs / user["user"]["id"] / row["document_id"]
    assert file.read_bytes() == raw
    file.write_bytes(b"X" * len(raw))
    target = tmp_path / "backup"
    backup(source, target, failure="DOCUMENT_CONTENT_MISMATCH")
    file.unlink()
    backup(source, target, failure="DOCUMENT_MISSING")
    assert not target.exists() and not file.exists()


def test_corrupt_bundle_fails_restore_without_publishing(source, tmp_path, monkeypatch):
    configure_roots(monkeypatch, source / "document_uploads", source / "vault_uploads")
    user = account("corrupt@example.com")
    item = client.post("/api/v1/vault/items", headers=head(user), data={"consent": "true"},
                       files={"file": ("sample.txt", b"AAA", "text/plain")}).json()["data"]
    relative = Path("vault_uploads") / user["user"]["id"] / item["id"]
    bundle, restored = tmp_path / "backup", tmp_path / "restored"
    backup(source, bundle)
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["vault_uploads"][relative.relative_to("vault_uploads").as_posix()]["sha256"] == (
        hashlib.sha256(b"AAA").hexdigest())
    (bundle / relative).write_bytes(b"BBB")
    invoke("verify", "--backup", bundle, failure="MANIFEST_MISMATCH")
    invoke("restore", "--backup", bundle, "--output", restored, failure="MANIFEST_MISMATCH")
    assert not restored.exists() and (source / relative).read_bytes() == b"AAA"


def test_existing_and_overlapping_outputs(source, tmp_path):
    bundle = tmp_path / "backup"
    backup(source, source / "nested", failure="OVERLAPPING_PATHS")
    backup(source, bundle)
    backup(source, bundle, failure="TARGET_EXISTS")
    target = tmp_path / "existing"
    target.mkdir()
    invoke("restore", "--backup", bundle, "--output", target, failure="TARGET_EXISTS")
    assert not list(target.iterdir())
    invoke("restore", "--backup", bundle, "--output", bundle / "child", failure="OVERLAPPING_PATHS")
    invoke("restore", "--backup", bundle, "--output", source / "child", failure="OUTPUT_IN_DATA_ROOT")
    invoke("verify", "--backup", bundle)


def test_linked_original_rejected(source, tmp_path):
    outside = tmp_path / "outside"
    outside.write_bytes(b"synthetic")
    owner = source / "document_uploads" / "owner"
    owner.mkdir(parents=True)
    (owner / "linked").hardlink_to(outside)
    backup(source, tmp_path / "backup", failure="ORIGINAL_TYPE_INVALID")
    assert outside.read_bytes() == b"synthetic" and not (tmp_path / "backup").exists()


def test_directory_link_cannot_redirect_originals_or_publication(source, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    clean_bundle = tmp_path / "clean-backup"
    backup(source, clean_bundle)
    link = source / "document_uploads"
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(outside), str(link))
    else:
        link.symlink_to(outside, target_is_directory=True)
    target = tmp_path / "backup"
    backup(source, target, failure="LINK_NOT_ALLOWED")
    invoke("restore", "--backup", clean_bundle, "--output", link / "nested", failure="LINK_NOT_ALLOWED")
    assert not target.exists() and not list(outside.iterdir())


def test_manifest_paths_cannot_select_restore_destination(source, tmp_path):
    bundle = tmp_path / "backup"
    backup(source, bundle)
    manifest = bundle / "manifest.json"
    contents = json.loads(manifest.read_text())
    contents["document_uploads"]["../../escaped"] = {"size": 0, "sha256": ""}
    manifest.write_text(json.dumps(contents))
    target = tmp_path / "restore"
    invoke("restore", "--backup", bundle, "--output", target, failure="MANIFEST_MISMATCH")
    assert not target.exists() and not (tmp_path / "escaped").exists()


def test_foreign_key_error_rejects_backup(source, tmp_path):
    with closing(sqlite3.connect(source / "ruleflow.db")) as db:
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute("CREATE TABLE rf051_bad_link(owner TEXT REFERENCES users(id))")
        db.execute("INSERT INTO rf051_bad_link VALUES ('absent-user')")
        db.commit()
    target = tmp_path / "backup"
    backup(source, target, failure="DATABASE_FOREIGN_KEY")
    assert not target.exists()


def test_redacted_copy_is_required_and_checked_against_its_stored_digest(source, tmp_path, monkeypatch):
    import fitz

    configure_roots(monkeypatch, source / "document_uploads", source / "vault_uploads")
    owner = account("backup-redaction@example.com")
    headers = head(owner)
    with fitz.open() as pdf:
        pdf.new_page().insert_text((40, 60), "Phone 13812345678")
        upload = ("synthetic.pdf", pdf.tobytes(), "application/pdf")
    imported, = client.post("/api/v1/imports/files", headers=headers, data={"consent": "true"},
                            files={"files": upload}).json()["data"]
    document = "/api/v1/documents/" + imported["document_id"]
    scan = client.post(document + "/privacy/scan", headers=headers).json()["data"]
    copy = client.post(document + "/redact", headers=headers, json={
        "revision": 1, "finding_ids": [scan["findings"][0]["id"]], "consent": True}).json()["data"]
    relative = Path("document_uploads") / owner["user"]["id"] / copy["id"]
    bundle, restored = tmp_path / "bundle", tmp_path / "restored"
    backup(source, bundle)
    invoke("verify", "--backup", bundle)
    invoke("restore", "--backup", bundle, "--output", restored)
    assert hashlib.sha256((restored / relative).read_bytes()).hexdigest() == copy["sha256"]

    # Equal length, different bytes; a fresh inventory alone would bless the changed copy.
    file = source / relative
    file.write_bytes(b"X" * file.stat().st_size)
    target = tmp_path / "bad-backup"
    backup(source, target, failure="DERIVATIVE_CONTENT_MISMATCH")
    file.unlink()
    backup(source, target, failure="DERIVATIVE_MISSING")
    assert not target.exists()
    (bundle / relative).unlink()
    invoke("verify", "--backup", bundle, failure="DERIVATIVE_MISSING")
    target = tmp_path / "bad-restore"
    invoke("restore", "--backup", bundle, "--output", target, failure="DERIVATIVE_MISSING")
    assert not target.exists()


def test_manifest_metadata_and_legacy_readback(source, tmp_path):
    bundle = tmp_path / "bundle"
    with closing(sqlite3.connect(source / "ruleflow.db")) as db:
        version, = db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    start = datetime.now(timezone.utc).replace(microsecond=0)
    backup(source, bundle)
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text())
    assert manifest["version"] == 2 and manifest["source_revision"] is None
    assert start <= datetime.fromisoformat(manifest["created_at_utc"]) <= datetime.now(timezone.utc)
    assert manifest["database_migration_version"] == version
    path.write_text(json.dumps(dict(manifest, database_migration_version=version + 1)))
    invoke("verify", "--backup", bundle, failure="MANIFEST_MISMATCH")
    path.write_text(json.dumps(dict(manifest, created_at_utc="unknown")))
    invoke("verify", "--backup", bundle, failure="MANIFEST_METADATA")
    legacy = {key: manifest[key] for key in ("ruleflow.db", "document_uploads", "vault_uploads")}
    path.write_text(json.dumps(dict(legacy, version=1)))
    invoke("verify", "--backup", bundle)
    invoke("restore", "--backup", bundle, "--output", tmp_path / "legacy-restore")


@pytest.mark.parametrize(("change", "error"), [
    ("DROP TABLE document_derivatives", "DATABASE_SCHEMA"),
    ("ALTER TABLE document_derivatives RENAME COLUMN sha256 TO bad_digest", "DATABASE_SCHEMA"),
    ("DELETE FROM schema_migrations", "DATABASE_MIGRATION_VERSION"),
])
def test_incomplete_database_rejected(source, tmp_path, change, error):
    with closing(sqlite3.connect(source / "ruleflow.db")) as db:
        db.execute(change)
        db.commit()
    target = tmp_path / "backup"
    backup(source, target, failure=error)
    assert not target.exists()
