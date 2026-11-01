import io
from PIL import Image
import rapidocr_onnxruntime
from app.parsing import parse_bytes

def test_quarter_turn_ocr_restores_original_evidence_coordinates(monkeypatch):
    class Engine:
        def __init__(self,**kwargs):self.calls=0
        def __call__(self,image):
            self.calls+=1
            if self.calls==1:return [[[[1,1],[3,1],[3,18],[1,18]],'原图识别',.7]],None
            return [[[[1,1],[18,1],[18,3],[1,3]],'完整通知文字',.98 if self.calls==2 else .9]],None
    monkeypatch.setattr(rapidocr_onnxruntime,'RapidOCR',Engine)
    content=io.BytesIO();Image.new('RGB',(10,20),'white').save(content,format='PNG')
    rows=parse_bytes(content.getvalue(),'image/png','test.png')
    assert rows[0]['text']=='完整通知文字'
    assert rows[0]['page_width']==10 and rows[0]['page_height']==20
    assert all(0<=x<10 and 0<=y<20 for x,y in rows[0]['bbox'])
