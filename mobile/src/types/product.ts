export type BackendStatus='CONNECTED'|'PARTIAL'|'MISSING'|'LOCAL_ONLY'|'DEMO_ONLY';

export interface EvidenceSource {
  id?:string|null;
  sourceType?:string|null;
  title?:string|null;
  publisher?:string|null;
  effectiveDate?:string|null;
  matchedSection?:string|null;
  quote?:string|null;
  context?:string|null;
  confidence?:number|null;
  url?:string|null;
  fileRef?:string|null;
  locator?:string|null;
  page?:number|null;
}

export interface KnowledgeEvidence extends EvidenceSource {
  ruleId?:string|null;
  ruleLabel?:string|null;
  effective_date?:string|null;
  matched_section?:string|null;
  match_type?:string|null;
  match_score?:number|null;
  evidence_ids?:string[];
  reference?:{document_id:string;version:string;locator:string;section_id?:string};
}

export interface ScheduleItem {
  id?:string|null;
  case_id?:string|null;
  taskId?:string|null;
  task_id?:string|null;
  title?:string|null;
  kind?:'busy'|'course'|'task'|null;
  startsAt?:string|null;
  endsAt?:string|null;
  starts_at?:string|null;
  ends_at?:string|null;
  status?:string|null;
}

export interface VaultItem {
  id:string;
  name:string;
  category:string;
  mime:string;
  size:number;
  created_at:string;
  updated_at:string;
  case_ids:string[];
  task_ids:string[];
  content_url:string;
}

export interface PrivacyFinding {
  id?:string|null;
  type?:string|null;
  original?:string|null;
  redacted?:string|null;
  start?:number|null;
  end?:number|null;
}

export type ImportDraftSource=
  | {id:'text';kind:'text';label:string;detail:string}
  | {id:'url';kind:'url';label:string;detail:string}
  | {id:string;kind:'file';label:string;detail:string;file:File}
  | {id:'share';kind:'share';label:string;detail:string};

export interface ImportBatchSource {
  id:string;
  batch_id:string;
  kind:'text'|'url'|'file';
  name:string;
  status:'ready'|'completed'|'failed';
  reason:'source_failed'|null;
  error:string|null;
  metadata:Record<string,unknown>;
  evidence_id:string|null;
  created_at:string;
  updated_at:string;
}

export interface ImportBatch {
  id:string;
  title:string|null;
  state:'draft'|'queued'|'processing'|'completed'|'partial_failure'|'failed';
  revision:number;
  created_at:string;
  updated_at:string;
  started_at:string|null;
  processing_at:string|null;
  completed_at:string|null;
  source_count:number;
  ready_source_count:number;
  analyzable_source_count:number;
  successful_source_count:number;
  failed_source_count:number;
  sources:ImportBatchSource[];
  can_add_sources:boolean;
  case_id:string|null;
  result:any|null;
}

export interface ImportSourceListItem {
  id:string;
  kind:string;
  label:string;
  detail:string;
  status?:string;
  error?:string|null;
  removable?:boolean;
}
