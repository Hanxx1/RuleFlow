"""Validate local Markdown links/images without contacting external services."""
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

root = Path(__file__).resolve().parents[1]
names = subprocess.check_output(
    ['git', '-C', str(root), 'ls-files', '--cached', '--others', '--exclude-standard', '-z']
).decode().split('\0')
checked = 0
errors = []
for name in sorted(set(names)):
    source = root / name
    if source.suffix != '.md' or not source.is_file():
        continue
    text = source.read_text(encoding='utf-8-sig')
    targets = re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text)
    targets += re.findall(r'^\s*\[[^\]]+\]:\s*(\S+)', text, flags=re.MULTILINE)
    targets += re.findall(r'<(?:img|a)\b[^>]*(?:src|href)=["\']([^"\']+)', text)
    for target in targets:
        target = target.strip().strip('<>')
        if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', target) or target.startswith(('#', '//')):
            continue
        path = unquote(target.split('#', 1)[0].split('?', 1)[0])
        if not path:
            continue
        destination = (source.parent / path).resolve()
        checked += 1
        if not destination.is_relative_to(root) or not destination.exists():
            errors.append(f'{name}: {target}')
if errors:
    raise SystemExit('Broken local document links:\n' + '\n'.join(errors))
print(f'PASS {checked} local Markdown link/image targets exist; external URLs not checked')
