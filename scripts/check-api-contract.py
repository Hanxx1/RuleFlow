"""Compare the full OpenAPI contract against the accepted baseline fingerprint."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'server'))
with tempfile.TemporaryDirectory(prefix='ruleflow-contract-') as temporary:
    os.environ.update(DATABASE_PATH=':memory:', DEMO_MODE='false', VAULT_UPLOAD_ROOT=temporary)
    from app.main import app
    encoded = json.dumps(app.openapi(), sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    actual = hashlib.sha256(encoded).hexdigest()
    expected = (root / 'docs/testing/api-contract.sha256').read_text().strip()
    if actual != expected:
        raise SystemExit(f'API contract changed: {actual} != {expected}')
    print(f'PASS OpenAPI contract matches accepted baseline: {actual}')
