"""Real HTTP startup from an unrelated cwd, with disposable synthetic data."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid


root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='ruleflow-startup-') as temporary:
    folder = Path(temporary)
    environment = dict(os.environ, APP_ENV='development', DEMO_MODE='false',
                       DATABASE_PATH=str(folder / 'test.db'),
                       VAULT_UPLOAD_ROOT=str(folder / 'vault'),
                       DOCUMENT_UPLOAD_ROOT=str(folder / 'documents'),
                       LLM_BASE_URL='', LLM_MODEL='', LLM_API_KEY='',
                       REFRESH_TOKEN_PEPPER=uuid.uuid4().hex,
                       PYTHONDONTWRITEBYTECODE='1')
    with socket.socket() as available:
        available.bind(('127.0.0.1', 0))
        port = available.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    process = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', 'app.main:app', '--app-dir', str(root / 'server'),
         '--host', '127.0.0.1', '--port', str(port)],
        cwd=folder, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
    )
    # Ignore workstation proxy settings for this loopback-only verification.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path, body=None, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        data = json.dumps(body).encode() if body is not None else None
        with opener.open(urllib.request.Request(origin + path, data=data, headers=headers), timeout=5) as response:
            return json.load(response)['data']

    try:
        for attempt in range(100):
            try:
                assert request('/health')['status'] == 'ok'
                break
            except (OSError, AssertionError):
                if process.poll() is not None:
                    raise RuntimeError('Startup exited before health became ready')
                time.sleep(0.1)
        else:
            raise RuntimeError('Startup health timeout')
        credentials = {'email': f'portable-{uuid.uuid4().hex}@example.com',
                       'password': uuid.uuid4().hex}
        registered = request('/api/v1/auth/register', credentials)
        request('/api/v1/auth/verify', {'token': registered['development_verification_token']})
        token = request('/api/v1/auth/login', credentials)['access_token']
        case = request('/api/v1/cases', {'title': 'Synthetic portability check'}, token)
        assert request('/api/v1/cases/' + case['id'], token=token)['id'] == case['id']
        print('PASS real HTTP startup, health, registration, login and case roundtrip from unrelated cwd')
    finally:
        process.terminate()
        process.communicate(timeout=10)
