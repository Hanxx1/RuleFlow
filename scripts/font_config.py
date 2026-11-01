"""Optional OCR corpus font configuration, independent of the developer drive."""
import os
from pathlib import Path

def corpus_font():
    configured = os.environ.get('ZHISHI_TEST_FONT')
    if configured:
        path = Path(configured).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError('ZHISHI_TEST_FONT must be an existing CJK font')
        return str(path)
    windows = os.environ.get('WINDIR')
    if windows:
        path = Path(windows) / 'Fonts' / 'msyh.ttc'
        if path.is_file():
            return str(path)
    raise RuntimeError('Set ZHISHI_TEST_FONT to a CJK-capable font for OCR corpus scripts')
