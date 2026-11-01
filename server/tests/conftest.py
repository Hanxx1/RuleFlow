"""No production DB, user uploads or live model calls are used by the core suite."""
import os
import tempfile
from pathlib import Path
from dataclasses import replace
import sys

import pytest

_collection_root = tempfile.TemporaryDirectory(prefix='ruleflow-tests-')
os.environ.update(DATABASE_PATH=':memory:', DEMO_MODE='false', APP_ENV='development',
                  LLM_BASE_URL='', LLM_MODEL='', LLM_API_KEY='',
                  VAULT_UPLOAD_ROOT=str(Path(_collection_root.name) / 'vault'),
                  DEMO_UPLOAD_ROOT=str(Path(_collection_root.name) / 'demo'),
                  DOCUMENT_UPLOAD_ROOT=str(Path(_collection_root.name) / 'documents'))

@pytest.fixture(autouse=True)
def isolated_application(monkeypatch, tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("application")
    from app import auth, settings
    from app.main import app
    from fastapi.testclient import TestClient
    from helpers import client

    if auth._memory_connection is not None:
        auth._memory_connection.close()
    auth._memory_connection = None
    monkeypatch.setattr(auth, 'DB', ':memory:')
    current = settings.SETTINGS
    isolated = replace(current, vault_upload_root=tmp_path / 'vault',
                       demo_upload_root=tmp_path / 'demo')
    # Existing modules import the immutable settings object directly.
    # Patch its owners in tests rather than changing production lifecycles.
    for name, module in list(sys.modules.items()):
        if name.startswith('app.') and getattr(module, 'SETTINGS', None) is current:
            monkeypatch.setattr(module, 'SETTINGS', isolated)
    monkeypatch.setenv('DOCUMENT_UPLOAD_ROOT', str(tmp_path / 'documents'))
    monkeypatch.setenv('DEMO_DOCUMENT_ROOT', str(tmp_path / 'demo' / 'documents'))
    with TestClient(app) as active:
        client.target = active
        try:
            yield
        finally:
            client.target = None
    if auth._memory_connection is not None:
        auth._memory_connection.close()
        auth._memory_connection = None


def pytest_unconfigure(config):
    _collection_root.cleanup()
