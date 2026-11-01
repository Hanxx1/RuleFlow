"""Existing schema initialization, extracted without changing its order."""
from .auth import init, conn
from .migrations import apply_migrations

def database():
 init()
 with conn() as c:c.executescript("""
 CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,title TEXT NOT NULL,category TEXT NOT NULL,status TEXT NOT NULL,relevance TEXT NOT NULL DEFAULT 'UNKNOWN',deadline TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,deadline_source TEXT,deadline_evidence_ids_json TEXT NOT NULL DEFAULT '[]',FOREIGN KEY(owner_id) REFERENCES users(id));
 CREATE TABLE IF NOT EXISTS facts(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT,key TEXT NOT NULL,value_json TEXT NOT NULL,source TEXT NOT NULL,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,source_name TEXT NOT NULL,text TEXT NOT NULL,locator TEXT,page INTEGER,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS rules(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,label TEXT NOT NULL,ast_json TEXT NOT NULL,evidence_ids_json TEXT NOT NULL,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,deadline TEXT,evidence_ids_json TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,duration_minutes INTEGER);
 CREATE TABLE IF NOT EXISTS imports(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,kind TEXT NOT NULL,name TEXT,state TEXT NOT NULL,privacy_json TEXT NOT NULL,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS analysis_jobs(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,import_id TEXT NOT NULL,state TEXT NOT NULL,stage TEXT NOT NULL,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS materials(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,title TEXT NOT NULL,state TEXT NOT NULL,evidence_ids_json TEXT NOT NULL,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS task_edges(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,before_task_id TEXT NOT NULL,after_task_id TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS conflicts(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,field TEXT NOT NULL,left_evidence_id TEXT NOT NULL,right_evidence_id TEXT NOT NULL,state TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS analysis_metadata(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,mode TEXT NOT NULL,model_id TEXT NOT NULL,prompt_version TEXT NOT NULL,parser_version TEXT NOT NULL,input_hash TEXT NOT NULL,cost_summary TEXT,summary TEXT NOT NULL,questions_json TEXT NOT NULL,review_reasons_json TEXT NOT NULL,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS sync_operations(owner_id TEXT NOT NULL,operation_id TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(owner_id,operation_id));
 CREATE TABLE IF NOT EXISTS sync_changes(cursor INTEGER PRIMARY KEY AUTOINCREMENT,owner_id TEXT NOT NULL,entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,version INTEGER NOT NULL,payload_json TEXT NOT NULL,deleted_at TEXT,created_at TEXT NOT NULL);
 """);apply_migrations(c)
