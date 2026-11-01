"""Independent bounded validation before storing or decoding a document."""
import io
import zipfile
import math
from pathlib import Path

EXTENSIONS = {'text/plain': {'.txt'}, 'text/html': {'.html', '.htm'}, 'application/xhtml+xml': {'.html', '.xhtml'},
              'application/pdf': {'.pdf'}, 'image/png': {'.png'}, 'image/jpeg': {'.jpg', '.jpeg'},
              'application/vnd.ms-excel': {'.xls'},
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document': {'.docx'},
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': {'.xlsx'}}


class DocumentError(ValueError):
    def __init__(self, code, message, status=422):
        self.code, self.status = code, status
        super().__init__(message)


def validate_file(raw: bytes, mime: str, name: str = ''):
    if mime not in EXTENSIONS or (name and Path(name).suffix.lower() not in EXTENSIONS[mime]):
        raise DocumentError('FILE_UNSUPPORTED', '文件扩展名与类型不一致或不受支持', 415)
    limit = (10 if mime.startswith('image/') else 20) * 1024 * 1024
    if not raw or len(raw) > limit:
        raise DocumentError('FILE_TOO_LARGE' if raw else 'FILE_EMPTY', '文件为空或超过格式体积限制', 413 if raw else 422)
    signatures = {'application/pdf': b'%PDF-', 'image/png': b'\x89PNG\r\n\x1a\n', 'image/jpeg': b'\xff\xd8',
                  'application/vnd.ms-excel': b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'}
    if mime in signatures and not raw.startswith(signatures[mime]):
        raise DocumentError('FILE_CORRUPTED', '文件内容与声明格式不一致')
    if mime.endswith(('wordprocessingml.document', 'spreadsheetml.sheet')):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries = archive.infolist()
                required = 'word/document.xml' if mime.endswith('wordprocessingml.document') else 'xl/workbook.xml'
                if required not in archive.namelist() or len(entries) > 10000 or sum(item.file_size for item in entries) > 64 * 1024 * 1024:
                    raise ValueError()
        except (zipfile.BadZipFile, ValueError):
            raise DocumentError('FILE_CORRUPTED', 'Office文件无效或展开体积超限')
    if mime.startswith('image/'):
        from PIL import Image
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.width * image.height > 20_000_000:
                    raise DocumentError('IMAGE_TOO_LARGE', '图片像素总量超过限制')
                image.verify()
        except DocumentError:
            raise
        except Exception:
            raise DocumentError('FILE_CORRUPTED', '图片无法读取')
    if mime == 'application/pdf':
        import fitz
        try:
            with fitz.open(stream=raw, filetype='pdf') as document:
                if document.needs_pass:
                    raise DocumentError('PDF_ENCRYPTED', '加密PDF需要先解密')
                if len(document) > 20:
                    raise DocumentError('PDF_TOO_MANY_PAGES', 'PDF最多支持20页')
                if any(not math.isfinite(page.rect.width*page.rect.height) or page.rect.width*page.rect.height*1.7**2>20_000_000 for page in document):
                    raise DocumentError('PDF_PAGE_TOO_LARGE','PDF页面渲染像素超过处理预算')
        except DocumentError:
            raise
        except Exception:
            raise DocumentError('FILE_CORRUPTED', 'PDF无法读取')


async def read_upload(upload, max_bytes=20 * 1024 * 1024):
    result = bytearray()
    while chunk := await upload.read(65536):
        result.extend(chunk)
        if len(result) > max_bytes:
            raise DocumentError('FILE_TOO_LARGE', '文件超过读取限制', 413)
    return bytes(result)
