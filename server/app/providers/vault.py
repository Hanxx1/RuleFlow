"""Vault content providers. Database metadata never contains a local path."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..settings import SETTINGS


ROOT = Path(__file__).resolve().parents[3]
DEMO_FILES_ROOT = ROOT / "shared" / "demo" / "files"


class VaultContentProvider(Protocol):
    def put(self, owner_id: str, item_id: str, content: bytes) -> tuple[str, str]: ...
    def read(self, owner_id: str, provider: str, key: str) -> bytes: ...
    def delete(self, owner_id: str, provider: str, key: str) -> None: ...


def _safe_child(root: Path, *parts: str) -> Path:
    root = root.resolve()
    target = root.joinpath(*parts).resolve()
    if target == root or root not in target.parents:
        raise ValueError("invalid vault content key")
    return target


class LocalVaultContentProvider:
    def __init__(self, upload_root: Path, fixture_root: Path | None = None):
        self.upload_root = upload_root.resolve()
        self.fixture_root = fixture_root.resolve() if fixture_root else None

    def put(self, owner_id: str, item_id: str, content: bytes) -> tuple[str, str]:
        target = _safe_child(self.upload_root, owner_id, item_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return "local", item_id

    def read(self, owner_id: str, provider: str, key: str) -> bytes:
        if provider == "local":
            target = _safe_child(self.upload_root, owner_id, key)
        elif provider == "fixture" and self.fixture_root:
            target = _safe_child(self.fixture_root, key)
        else:
            raise FileNotFoundError("vault content provider unavailable")
        if not target.is_file():
            raise FileNotFoundError("vault content missing")
        return target.read_bytes()

    def delete(self, owner_id: str, provider: str, key: str) -> None:
        if provider != "local":
            return
        target = _safe_child(self.upload_root, owner_id, key)
        if target.exists():
            target.unlink()
        owner_root = _safe_child(self.upload_root, owner_id)
        if owner_root.exists() and not any(owner_root.iterdir()):
            owner_root.rmdir()


def get_vault_content_provider() -> VaultContentProvider:
    if SETTINGS.demo_mode:
        return LocalVaultContentProvider(SETTINGS.demo_upload_root, DEMO_FILES_ROOT)
    return LocalVaultContentProvider(SETTINGS.vault_upload_root)
