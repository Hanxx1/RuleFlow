"""Existing HTTP input contracts; field semantics are unchanged."""
from __future__ import annotations
from pydantic import BaseModel, Field

class CaseIn(BaseModel):title:str=Field(min_length=1,max_length=300);category:str='other';status:str='draft';deadline:str|None=None

class CasePatch(BaseModel):title:str|None=Field(default=None,min_length=1,max_length=300);category:str|None=None;status:str|None=None;deadline:str|None=None

class FactIn(BaseModel):key:str=Field(pattern=r'^profile\.[a-z_]+$');value:object;scope:str='case';valid_until:str|None=None

class TaskIn(BaseModel):title:str=Field(min_length=1,max_length=300);deadline:str|None=None;duration_minutes:int|None=Field(default=None,ge=1,le=1440);evidence_ids:list[str]=[]

class PatchTask(BaseModel):status:str

class TextImport(BaseModel):text:str=Field(min_length=1,max_length=200000);title:str|None=None;consent:bool=False

class UrlImport(BaseModel):url:str=Field(min_length=8,max_length=2048);title:str|None=None;consent:bool=False;include_attachments:bool=True

class ImportBatchIn(BaseModel):title:str|None=Field(default=None,max_length=300)

class EdgeIn(BaseModel):before_task_id:str;after_task_id:str

class MaterialIn(BaseModel):title:str=Field(min_length=1,max_length=300);evidence_ids:list[str]

class SyncChange(BaseModel):entity_type:str;entity_id:str;version:int;payload:dict={};deleted:bool=False

class SyncPush(BaseModel):operation_id:str=Field(min_length=8,max_length=128);changes:list[SyncChange]

class ProfileIn(BaseModel):facts:dict[str,object];valid_until:dict[str,str|None]=Field(default_factory=dict)

class PrivacyIn(BaseModel):text:str=Field(min_length=1,max_length=200000)

class AccountSettingsPatch(BaseModel):display_name:str|None=Field(default=None,max_length=100);locale:str|None=Field(default=None,min_length=2,max_length=16);timezone:str|None=Field(default=None,min_length=1,max_length=64)

class ScheduleItemIn(BaseModel):title:str=Field(min_length=1,max_length=200);kind:str;starts_at:str;ends_at:str;case_id:str|None=None;task_id:str|None=None

class ScheduleItemPatch(BaseModel):title:str|None=Field(default=None,min_length=1,max_length=200);kind:str|None=None;starts_at:str|None=None;ends_at:str|None=None;case_id:str|None=None;task_id:str|None=None

class SchedulePreferencesIn(BaseModel):work_start_hour:int=Field(default=8,ge=0,le=22,strict=True);work_end_hour:int=Field(default=21,ge=1,le=23,strict=True);buffer_minutes:int=Field(default=0,ge=0,le=120,strict=True);daily_max_minutes:int=Field(default=780,ge=30,le=1380,strict=True)

class CalendarBlockIn(BaseModel):
 model_config={'extra':'forbid'}
 id:str=Field(max_length=200)
 starts_at:str
 ends_at:str
 evidence_ids:list[str]=Field(min_length=1,max_length=5)

class SchedulePreviewIn(BaseModel):case_id:str|None=None;task_ids:list[str]=Field(default_factory=list);window_start:str|None=None;window_end:str|None=None;timezone:str='Asia/Shanghai';preferences:SchedulePreferencesIn=Field(default_factory=SchedulePreferencesIn);calendar_blocks:list[CalendarBlockIn]=Field(default_factory=list,max_length=2000);calendar_consent:bool=False;calendar_revision:int|None=Field(default=None,ge=0)

class DraftCommitIn(BaseModel):consent:bool=False;calendar_revision:int|None=Field(default=None,ge=0)

class AttachmentImportIn(BaseModel):index:int=Field(ge=0,le=9);consent:bool=False

class TaskPlanningIn(BaseModel):duration_minutes:int=Field(ge=1,le=1440,strict=True);splittable:bool=False;min_chunk_minutes:int=Field(default=30,ge=30,le=240,strict=True);max_chunk_minutes:int=Field(default=60,ge=30,le=240,strict=True);importance:float=Field(default=0,ge=0,le=1);preference:float=Field(default=0,ge=0,le=1)

class ScheduleSeriesIn(ScheduleItemIn):count:int=Field(ge=2,le=13,strict=True);every_weeks:int=Field(default=1,ge=1,le=4,strict=True);timezone:str='Asia/Shanghai'

class ScheduleLockIn(BaseModel):locked:bool

class ProfileInterestsIn(BaseModel):categories:list[str]=Field(max_length=7)

class VaultPatch(BaseModel):name:str|None=Field(default=None,min_length=1,max_length=255);category:str|None=None;case_ids:list[str]|None=None;task_ids:list[str]|None=None

class ReviewConfirmation(BaseModel):
 revision:int=Field(ge=1)
 action_ids:list[str]=Field(default_factory=list,max_length=50)
 deadline_id:str|None=None
 manual_deadline:str|None=None
 no_deadline:bool=False
 consent:bool=False
 task_deadlines:dict[str,dict]=Field(default_factory=dict,max_length=50)

class KnowledgeTextIn(BaseModel):
 text:str=Field(min_length=1,max_length=200000)
 title:str=Field(min_length=1,max_length=300)
 category:str=Field(default='other',max_length=50)
 consent:bool=False

class KnowledgeSearchIn(BaseModel):
 query:str=Field(min_length=1,max_length=4000)
 top_k:int=Field(default=5,ge=1,le=10)
 category:str|None=None

class KnowledgeConsent(BaseModel):consent:bool=False

class RedactIn(BaseModel):
 revision:int=Field(ge=1)
 finding_ids:list[str]=Field(min_length=1,max_length=100)
 consent:bool=False
