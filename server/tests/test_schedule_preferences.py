from datetime import datetime
from app.services.schedule import preview_schedule


def instant(value):return datetime.fromisoformat(value)


def test_daily_cap_buffer_and_working_hours_respect_dependencies():
    tasks=[{'id':'a','case_id':'case','title':'准备','duration_minutes':60},{'id':'b','case_id':'case','title':'提交','duration_minutes':60}]
    edges=[{'before_task_id':'a','after_task_id':'b'}]
    result=preview_schedule(tasks,edges,[],instant('2026-10-20T08:00:00+08:00'),instant('2026-10-22T20:00:00+08:00'),'Asia/Shanghai',{'a':'todo','b':'todo'},{'work_start_hour':10,'work_end_hour':18,'daily_max_minutes':60,'buffer_minutes':15})
    assert result['suggestions'][0]['starts_at']=='2026-10-20T02:00:00Z'
    assert result['suggestions'][1]['starts_at']=='2026-10-21T02:00:00Z'


def test_existing_course_buffer_and_subminute_rounding():
    task={'id':'a','case_id':'case','title':'提交','duration_minutes':30}
    existing=[{'kind':'course','starts_at':'2026-10-20T09:00:00+08:00','ends_at':'2026-10-20T10:00:00+08:00'}]
    result=preview_schedule([task],[],existing,instant('2026-10-20T10:00:01+08:00'),instant('2026-10-20T20:00:00+08:00'),'Asia/Shanghai',{'a':'todo'},{'buffer_minutes':15})
    assert result['suggestions'][0]['starts_at']=='2026-10-20T02:30:00Z'


def test_existing_task_time_consumes_daily_cap():
    task={'id':'a','case_id':'case','title':'提交','duration_minutes':30}
    existing=[{'kind':'task','task_id':'other','starts_at':'2026-10-20T09:00:00+08:00','ends_at':'2026-10-20T10:00:00+08:00'}]
    result=preview_schedule([task],[],existing,instant('2026-10-20T10:00:00+08:00'),instant('2026-10-22T20:00:00+08:00'),'Asia/Shanghai',{'a':'todo'},{'daily_max_minutes':60})
    assert result['suggestions'][0]['starts_at']=='2026-10-21T00:00:00Z'
