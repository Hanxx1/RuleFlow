"""Runtime settings with a fail-closed Demo/Real storage boundary."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


SERVER_ROOT = Path(__file__).resolve().parents[1]


def _boolean(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _database_path(value: str) -> str | Path:
    if value == ":memory:":
        return value
    return Path(value).expanduser().resolve()


@dataclass(frozen=True)
class Settings:
    demo_mode: bool
    real_database_path: str | Path
    demo_database_path: str | Path
    database_path: str | Path
    demo_upload_root: Path
    vault_upload_root: Path

    @property
    def backend_mode(self) -> str:
        return "demo" if self.demo_mode else "real"


def resolve_settings(environment: Mapping[str, str]) -> Settings:
    demo_mode = _boolean(environment.get("DEMO_MODE"))
    real_path = _database_path(
        environment.get("DATABASE_PATH", str(SERVER_ROOT / "data" / "ruleflow.db"))
    )
    demo_path = _database_path(
        environment.get("DEMO_DATABASE_PATH", str(SERVER_ROOT / "data" / "demo.db"))
    )
    upload_root = Path(
        environment.get("DEMO_UPLOAD_ROOT", str(SERVER_ROOT / "data" / "demo_uploads"))
    ).expanduser().resolve()
    vault_upload_root = Path(
        environment.get("VAULT_UPLOAD_ROOT", str(SERVER_ROOT / "data" / "vault_uploads"))
    ).expanduser().resolve()

    if demo_mode and real_path == demo_path:
        raise RuntimeError("DEMO_DATABASE_PATH must differ from DATABASE_PATH")
    if demo_mode and upload_root == vault_upload_root:
        raise RuntimeError("DEMO_UPLOAD_ROOT must differ from VAULT_UPLOAD_ROOT")

    return Settings(
        demo_mode=demo_mode,
        real_database_path=real_path,
        demo_database_path=demo_path,
        database_path=demo_path if demo_mode else real_path,
        demo_upload_root=upload_root,
        vault_upload_root=vault_upload_root,
    )


SETTINGS = resolve_settings(os.environ)
