import io
import socket
import pytest
from PIL import Image
from docx import Document
from openpyxl import Workbook
from app.parsing import UnsafeHostError,parse_bytes,resolve_public_host
def test_parse_text_docx_xlsx():
 assert parse_bytes('通知正文'.encode(),'text/plain')[0]['text']=='通知正文'
 d=Document();d.add_paragraph('DOCX 通知');b=io.BytesIO();d.save(b);assert 'DOCX' in parse_bytes(b.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')[0]['text']
 w=Workbook();w.active['A1']='XLSX 通知';b=io.BytesIO();w.save(b);assert 'XLSX' in parse_bytes(b.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')[0]['text']
def test_image_ocr_path_returns_located_block_even_when_blank():
 b=io.BytesIO();Image.new('RGB',(180,60),'white').save(b,'PNG')
 blocks=parse_bytes(b.getvalue(),'image/png','blank.png')
 assert blocks and blocks[0]['locator']=='图片 OCR' and 'confidence' in blocks[0]

def dns_rows(*addresses):return [(socket.AF_INET6 if ':' in address else socket.AF_INET,socket.SOCK_STREAM,6 if ':' in address else 6,'',(address,0,0,0) if ':' in address else (address,0)) for address in addresses]

def test_private_localhost_link_local_and_reserved_addresses_are_rejected(monkeypatch):
 for host in ('127.0.0.1','169.254.1.2','198.18.0.57','::1'):
  with pytest.raises(UnsafeHostError):resolve_public_host(host,allow_proxy_synthetic=True)
 monkeypatch.setattr('app.parsing.socket.getaddrinfo',lambda *args,**kwargs:dns_rows('10.0.0.8'))
 with pytest.raises(UnsafeHostError):resolve_public_host('private.example')

def test_all_ipv4_and_ipv6_dns_answers_must_be_public(monkeypatch):
 monkeypatch.setattr('app.parsing.socket.getaddrinfo',lambda *args,**kwargs:dns_rows('93.184.216.34','2606:2800:220:1:248:1893:25c8:1946'))
 assert len(resolve_public_host('public.example'))==2
 monkeypatch.setattr('app.parsing.socket.getaddrinfo',lambda *args,**kwargs:dns_rows('93.184.216.34','169.254.1.2'))
 with pytest.raises(UnsafeHostError):resolve_public_host('mixed.example')
