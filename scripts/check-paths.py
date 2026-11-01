"""Check tracked active source for developer-specific drive/user paths."""
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
paths = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--cached', '--others', '--exclude-standard', '-z']).decode().split('\0')
issues = []
for name in sorted(set(paths)):
    path = root / name
    if not name.startswith(('server/app/', 'server/tests/', 'mobile/', 'scripts/', 'tools/', 'desktop/', 'harmony/')):
        continue
    if path.suffix not in {'.py', '.ps1', '.mjs', '.ts', '.vue', '.gradle', '.cs', '.json5'} or not path.is_file():
        continue
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if re.search(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/(?:Users|home)/[^ /]+/', line):
            issues.append(f'{name}:{number}')
if issues:
    raise SystemExit('Review absolute paths: ' + ', '.join(issues))
print('PASS active source has no workstation drive/user paths')
