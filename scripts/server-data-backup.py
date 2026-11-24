"""Offline RuleFlow server backup. All input trees and their parents must be trusted and quiescent."""
import argparse
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import sqlite3
import stat
import sys
import tempfile

DATABASE = "ruleflow.db"
DOCUMENTS = "document_uploads"
VAULT = "vault_uploads"
MANIFEST = "manifest.json"


class BackupError(Exception):
    """Only fixed error codes may be shown to operators."""


def check(condition, code):
    if not condition:
        raise BackupError(code)


def plain_path(path):
    # Reject links before resolving, including Windows directory junctions.
    check(".." not in path.parts, "PARENT_TRAVERSAL")
    path = path.absolute()
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        check(not stat.S_ISLNK(info.st_mode) and
              not (getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT),
              "LINK_NOT_ALLOWED")
    return path


def disjoint(first, second):
    check(first != second and first not in second.parents and second not in first.parents,
          "OVERLAPPING_PATHS")


def identifier(name):
    check(isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9-]+", name)
          and not PureWindowsPath(name).is_reserved(), "INVALID_STORAGE_KEY")
    return name


@contextmanager
def unpublished(target):
    # The parent must already exist with a private ACL on Windows.
    check(target.parent.is_dir(), "OUTPUT_PARENT_MISSING")
    check(not any((parent / ".git").exists() for parent in target.parents), "OUTPUT_IN_REPOSITORY")
    check(not target.exists(), "TARGET_EXISTS")
    with tempfile.TemporaryDirectory(dir=target.parent, prefix=".rf051-") as tmp:
        stage = Path(tmp) / "data"
        stage.mkdir(mode=0o700)
        yield stage
        # Exclusive reservation also prevents POSIX rename replacing an existing empty directory.
        if os.name == "nt":
            stage.rename(target)
        else:
            target.mkdir(mode=0o700)
            try:
                stage.replace(target)
            except OSError:
                target.rmdir()
                raise


def inventory_tree(root, destination=None):
    """Copy/hash actual owner/key entries; never interpret a manifest path as a filesystem path."""
    files = {}
    if destination is not None:
        destination.mkdir(mode=0o700)
    if not root.exists() and destination is not None:
        return files  # DB cross-check below decides whether an absent tree is valid.
    check(root.is_dir(), "ORIGINAL_ROOT_INVALID")
    for owner in root.iterdir():
        plain_path(owner)
        identifier(owner.name)
        check(owner.is_dir(), "ORIGINAL_LAYOUT_INVALID")
        if destination is not None:
            (destination / owner.name).mkdir(mode=0o700)
        for item in owner.iterdir():
            plain_path(item)
            identifier(item.name)
            check(item.is_file() and item.stat().st_nlink == 1, "ORIGINAL_TYPE_INVALID")
            record = fingerprint(item)
            if destination is not None:
                copied = destination / owner.name / item.name
                shutil.copyfile(item, copied)
                check(fingerprint(copied) == record, "COPY_MISMATCH")
            files[f"{owner.name}/{item.name}"] = record
    return files


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"size": path.stat().st_size, "sha256": digest.hexdigest()}


def readonly(path, immutable=False):
    check(path.is_file(), "DATABASE_MISSING")
    flags = "?mode=ro&immutable=1" if immutable else "?mode=ro"
    return closing(sqlite3.connect(path.as_uri() + flags, uri=True))


def validate_database(path, documents, vault):
    with readonly(path, immutable=True) as db:
        db.execute("PRAGMA trusted_schema=OFF")
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"schema_migrations", "users", "cases", "tasks", "evidence", "document_lines",
                    "documents", "vault_items"}
        check(required <= tables, "DATABASE_SCHEMA")
        try:
            version, = db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            check(type(version) is int and version > 0, "DATABASE_MIGRATION_VERSION")
            originals = db.execute("SELECT owner_id,id,size,sha256 FROM documents")
            items = db.execute("SELECT owner_id,content_provider,content_key,size FROM vault_items")
            # Migration 10 introduced redacted copies. Older snapshots may predate that table.
            derivatives = ()
            if version >= 10 or "document_derivatives" in tables:
                check("document_derivatives" in tables, "DATABASE_SCHEMA")
                derivatives = db.execute("SELECT owner_id,id,sha256 FROM document_derivatives")
        except sqlite3.OperationalError as exc:
            raise BackupError("DATABASE_SCHEMA") from exc
        check(db.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "DATABASE_INTEGRITY")
        check(db.execute("PRAGMA foreign_key_check").fetchone() is None, "DATABASE_FOREIGN_KEY")
        for owner, key, size, sha in originals:
            record = documents.get(f"{identifier(owner)}/{identifier(key)}")
            check(record is not None, "DOCUMENT_MISSING")
            check(record == {"size": size, "sha256": sha}, "DOCUMENT_CONTENT_MISMATCH")
        for owner, key, sha in derivatives:
            record = documents.get(f"{identifier(owner)}/{identifier(key)}")
            check(record is not None, "DERIVATIVE_MISSING")
            check(record["sha256"] == sha, "DERIVATIVE_CONTENT_MISMATCH")
        for owner, provider, key, size in items:
            check(provider == "local", "UNSUPPORTED_VAULT_PROVIDER")
            record = vault.get(f"{identifier(owner)}/{identifier(key)}")
            check(record is not None, "VAULT_MISSING")
            check(record["size"] == size, "VAULT_SIZE_MISMATCH")
        return version


def describe(root, documents, vault):
    version = validate_database(root / DATABASE, documents, vault)
    return {"database_migration_version": version, DATABASE: fingerprint(root / DATABASE),
            DOCUMENTS: documents, VAULT: vault}


def backup(args):
    source = plain_path(args.data_dir)
    db_path = plain_path(source / DATABASE)
    check(db_path.is_file(), "DATABASE_MISSING")
    check(db_path.stat().st_nlink == 1, "DATABASE_TYPE_INVALID")
    vault = plain_path(source / VAULT)
    documents = plain_path(args.document_root or source / DOCUMENTS)
    target = plain_path(args.output)
    disjoint(vault, documents)
    disjoint(db_path, documents)
    disjoint(target, source)
    disjoint(target, documents)
    # SQLite may consult adjacent journal files even through a read-only connection.
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = plain_path(Path(str(db_path) + suffix))
        if sidecar.exists():
            check(sidecar.is_file() and sidecar.stat().st_nlink == 1, "DATABASE_TYPE_INVALID")
    with unpublished(target) as stage:
        with readonly(db_path) as src, closing(sqlite3.connect(stage / DATABASE)) as dst:
            src.backup(dst)
            dst.execute("PRAGMA journal_mode=DELETE")
        doc_files = inventory_tree(documents, stage / DOCUMENTS)
        vault_files = inventory_tree(vault, stage / VAULT)
        manifest = describe(stage, doc_files, vault_files)
        manifest.update(version=2, created_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        source_revision=None)
        (stage / MANIFEST).write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return manifest


def inspect_bundle(root):
    check(root.is_dir(), "BUNDLE_MISSING")
    entries = {plain_path(entry).name for entry in root.iterdir()}
    check(entries == {MANIFEST, DATABASE, DOCUMENTS, VAULT}, "BUNDLE_LAYOUT_INVALID")
    for file in (root / MANIFEST, root / DATABASE):
        check(file.is_file() and file.stat().st_nlink == 1, "BUNDLE_FILE_INVALID")
    expected = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    check(isinstance(expected, dict) and type(expected.get("version")) is int
          and expected["version"] in (1, 2), "MANIFEST_VERSION")
    format_version = expected.pop("version")
    if format_version == 2:
        timestamp = expected.pop("created_at_utc", None)
        check(isinstance(timestamp, str), "MANIFEST_METADATA")
        try:
            datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as exc:
            raise BackupError("MANIFEST_METADATA") from exc
        check("source_revision" in expected and expected.pop("source_revision") is None
              and type(expected.get("database_migration_version")) is int, "MANIFEST_METADATA")
    actual = describe(root, inventory_tree(root / DOCUMENTS), inventory_tree(root / VAULT))
    if format_version == 1:
        # A legacy manifest has no migration field to compare. Still inspect its actual database.
        check("database_migration_version" not in expected, "MANIFEST_MISMATCH")
        expected["database_migration_version"] = actual["database_migration_version"]
    check(actual == expected, "MANIFEST_MISMATCH")
    return actual


def restore(root, target):
    disjoint(root, target)
    check(not any((parent / DATABASE).is_file() for parent in target.parents), "OUTPUT_IN_DATA_ROOT")
    manifest = inspect_bundle(root)
    with unpublished(target) as stage:
        shutil.copyfile(root / DATABASE, stage / DATABASE)
        documents = inventory_tree(root / DOCUMENTS, stage / DOCUMENTS)
        vault = inventory_tree(root / VAULT, stage / VAULT)
        check(describe(stage, documents, vault) == manifest, "RESTORE_MISMATCH")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    save = commands.add_parser("backup")
    save.add_argument("--data-dir", required=True, type=Path)
    save.add_argument("--document-root", type=Path, help="effective DOCUMENT_UPLOAD_ROOT override")
    save.add_argument("--output", required=True, type=Path)
    save.add_argument("--writers-stopped", action="store_true", required=True,
                      help="confirm all writers are stopped or this is an offline volume snapshot")
    for name in ("verify", "restore"):
        command = commands.add_parser(name)
        command.add_argument("--backup", required=True, type=Path)
        if name == "restore":
            command.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.command == "backup":
            manifest = backup(args)
        else:
            root = plain_path(args.backup)
            manifest = restore(root, plain_path(args.output)) if args.command == "restore" else inspect_bundle(root)
        print(f"{args.command} OK documents={len(manifest[DOCUMENTS])} vault={len(manifest[VAULT])}")
        return 0
    except BackupError as error:
        code = str(error)
    except (ValueError, RecursionError):
        code = "INVALID_DATA"
    except sqlite3.Error:
        code = "DATABASE_ERROR"
    except OSError:
        code = "FILESYSTEM_ERROR"
    print(f"{args.command} FAILED {code}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
