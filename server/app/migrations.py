"""Small, dependency-free SQLite migrations for the current backend."""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def _record(connection: sqlite3.Connection, version: int, name: str, source: str) -> None:
    checksum = hashlib.sha256(source.encode("utf-8")).hexdigest()
    connection.execute(
        "INSERT INTO schema_migrations(version,name,checksum,applied_at) VALUES(?,?,?,?)",
        (version, name, checksum, _stamp()),
    )


def apply_migrations(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations(
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        checksum TEXT NOT NULL,
        applied_at TEXT NOT NULL
        )"""
    )
    applied = {
        row[0] for row in connection.execute("SELECT version FROM schema_migrations")
    }

    if 1 not in applied:
        source = "sessions.token_type access|refresh; legacy device_name=access backfill"
        if "token_type" not in _columns(connection, "sessions"):
            connection.execute(
                "ALTER TABLE sessions ADD COLUMN token_type TEXT NOT NULL DEFAULT 'refresh'"
            )
        connection.execute(
            "UPDATE sessions SET token_type='access' WHERE device_name='access'"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_type ON sessions(user_id,token_type,revoked_at)"
        )
        _record(connection, 1, "session_token_type", source)

    if 2 not in applied:
        source = "demo_seed_state(owner_id, fixture_version, seeded_at)"
        connection.execute(
            """CREATE TABLE IF NOT EXISTS demo_seed_state(
            owner_id TEXT PRIMARY KEY,
            fixture_version TEXT NOT NULL,
            seeded_at TEXT NOT NULL,
            FOREIGN KEY(owner_id) REFERENCES users(id)
            )"""
        )
        _record(connection, 2, "demo_seed_state", source)

    # Business tables are still created by main.database(). Auth initialization
    # runs first, so defer this migration until those tables exist.
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if 3 not in applied and {"cases", "tasks"}.issubset(tables):
        source = (
            "case deadline provenance; task duration; task-material links; "
            "account settings; Phase 2 query indexes"
        )
        if "deadline_source" not in _columns(connection, "cases"):
            connection.execute("ALTER TABLE cases ADD COLUMN deadline_source TEXT")
        if "deadline_evidence_ids_json" not in _columns(connection, "cases"):
            connection.execute(
                "ALTER TABLE cases ADD COLUMN deadline_evidence_ids_json TEXT NOT NULL DEFAULT '[]'"
            )
        connection.execute(
            "UPDATE cases SET deadline_source='generated' "
            "WHERE deadline IS NOT NULL AND deadline_source IS NULL"
        )
        if "duration_minutes" not in _columns(connection, "tasks"):
            connection.execute("ALTER TABLE tasks ADD COLUMN duration_minutes INTEGER")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS task_material_links(
              owner_id TEXT NOT NULL,
              task_id TEXT NOT NULL,
              material_id TEXT NOT NULL,
              PRIMARY KEY(owner_id,task_id,material_id),
              FOREIGN KEY(task_id) REFERENCES tasks(id),
              FOREIGN KEY(material_id) REFERENCES materials(id)
            );
            CREATE TABLE IF NOT EXISTS account_settings(
              owner_id TEXT PRIMARY KEY,
              display_name TEXT,
              locale TEXT NOT NULL DEFAULT 'zh-CN',
              timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(owner_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_cases_owner_status ON cases(owner_id,status);
            CREATE INDEX IF NOT EXISTS idx_cases_owner_category ON cases(owner_id,category);
            CREATE INDEX IF NOT EXISTS idx_cases_owner_deadline ON cases(owner_id,deadline);
            CREATE INDEX IF NOT EXISTS idx_tasks_owner_case_status ON tasks(owner_id,case_id,status);
            """
        )
        _record(connection, 3, "phase2_core_fields", source)

    if 4 not in applied and {"cases", "tasks", "materials"}.issubset(tables):
        source = (
            "schedule items; vault metadata and owner-scoped case/task links; "
            "content provider keys"
        )
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schedule_items(
              id TEXT PRIMARY KEY,
              owner_id TEXT NOT NULL,
              case_id TEXT,
              task_id TEXT,
              title TEXT NOT NULL,
              kind TEXT NOT NULL,
              starts_at TEXT NOT NULL,
              ends_at TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(owner_id) REFERENCES users(id),
              FOREIGN KEY(case_id) REFERENCES cases(id),
              FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            CREATE TABLE IF NOT EXISTS vault_items(
              id TEXT PRIMARY KEY,
              owner_id TEXT NOT NULL,
              name TEXT NOT NULL,
              category TEXT NOT NULL,
              mime TEXT NOT NULL,
              size INTEGER NOT NULL,
              content_provider TEXT NOT NULL,
              content_key TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(owner_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS vault_case_links(
              owner_id TEXT NOT NULL,
              vault_item_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              PRIMARY KEY(owner_id,vault_item_id,case_id),
              FOREIGN KEY(vault_item_id) REFERENCES vault_items(id),
              FOREIGN KEY(case_id) REFERENCES cases(id)
            );
            CREATE TABLE IF NOT EXISTS vault_task_links(
              owner_id TEXT NOT NULL,
              vault_item_id TEXT NOT NULL,
              task_id TEXT NOT NULL,
              PRIMARY KEY(owner_id,vault_item_id,task_id),
              FOREIGN KEY(vault_item_id) REFERENCES vault_items(id),
              FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            CREATE INDEX IF NOT EXISTS idx_schedule_owner_time
              ON schedule_items(owner_id,starts_at,ends_at);
            CREATE INDEX IF NOT EXISTS idx_schedule_owner_case
              ON schedule_items(owner_id,case_id);
            CREATE INDEX IF NOT EXISTS idx_vault_owner_category
              ON vault_items(owner_id,category,created_at);
            CREATE INDEX IF NOT EXISTS idx_vault_case_owner
              ON vault_case_links(owner_id,case_id);
            CREATE INDEX IF NOT EXISTS idx_vault_task_owner
              ON vault_task_links(owner_id,task_id);
            """
        )
        _record(connection, 4, "schedule_and_vault", source)

    if 5 not in applied and {"cases", "evidence", "imports"}.issubset(tables):
        source = (
            "owner-scoped import batches and sources; deterministic analysis timing; "
            "source evidence traceability and revision idempotency"
        )
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS import_batches(
              id TEXT PRIMARY KEY,
              owner_id TEXT NOT NULL,
              title TEXT,
              state TEXT NOT NULL,
              revision INTEGER NOT NULL DEFAULT 0,
              analyzed_revision INTEGER,
              started_at TEXT,
              demo_processing_at TEXT,
              demo_completed_at TEXT,
              final_status TEXT,
              case_id TEXT,
              result_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(owner_id) REFERENCES users(id),
              FOREIGN KEY(case_id) REFERENCES cases(id)
            );
            CREATE TABLE IF NOT EXISTS import_sources(
              id TEXT PRIMARY KEY,
              owner_id TEXT NOT NULL,
              batch_id TEXT NOT NULL,
              kind TEXT NOT NULL,
              name TEXT NOT NULL,
              status TEXT NOT NULL,
              error TEXT,
              metadata_json TEXT NOT NULL,
              extracted_text TEXT,
              evidence_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(owner_id) REFERENCES users(id),
              FOREIGN KEY(batch_id) REFERENCES import_batches(id),
              FOREIGN KEY(evidence_id) REFERENCES evidence(id)
            );
            CREATE TABLE IF NOT EXISTS import_analysis_runs(
              id TEXT PRIMARY KEY,
              owner_id TEXT NOT NULL,
              batch_id TEXT NOT NULL,
              revision INTEGER NOT NULL,
              final_status TEXT NOT NULL,
              result_json TEXT NOT NULL,
              started_at TEXT NOT NULL,
              processing_at TEXT NOT NULL,
              completed_at TEXT NOT NULL,
              UNIQUE(owner_id,batch_id,revision),
              FOREIGN KEY(owner_id) REFERENCES users(id),
              FOREIGN KEY(batch_id) REFERENCES import_batches(id)
            );
            CREATE INDEX IF NOT EXISTS idx_import_batches_owner_updated
              ON import_batches(owner_id,updated_at);
            CREATE INDEX IF NOT EXISTS idx_import_sources_owner_batch
              ON import_sources(owner_id,batch_id,created_at);
            CREATE INDEX IF NOT EXISTS idx_import_runs_owner_batch
              ON import_analysis_runs(owner_id,batch_id,revision);
            """
        )
        _record(connection, 5, "import_batches", source)

    if 6 not in applied and {"cases", "analysis_metadata"}.issubset(tables):
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS case_reviews(
              owner_id TEXT NOT NULL,case_id TEXT NOT NULL,revision INTEGER NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('needs_confirmation','confirmed')),
              candidate_json TEXT NOT NULL,decision_json TEXT,confirmed_at TEXT,
              PRIMARY KEY(owner_id,case_id),FOREIGN KEY(case_id) REFERENCES cases(id)
            );
            CREATE TABLE IF NOT EXISTS review_events(
              id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT NOT NULL,
              revision INTEGER NOT NULL,action TEXT NOT NULL,details_json TEXT NOT NULL,
              created_at TEXT NOT NULL,FOREIGN KEY(case_id) REFERENCES cases(id)
            );
            CREATE INDEX IF NOT EXISTS idx_review_events_owner_case ON review_events(owner_id,case_id);
        """)
        _record(connection, 6, "analysis_review_gate", "case reviews; candidate snapshot; atomic confirmation and audit")

    if 7 not in applied and {'evidence','imports'}.issubset(tables):
        connection.executescript('''
          CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,name TEXT NOT NULL,mime TEXT NOT NULL,sha256 TEXT NOT NULL,size INTEGER NOT NULL,status TEXT NOT NULL,error_code TEXT,created_at TEXT NOT NULL,revision INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS document_lines(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,document_id TEXT NOT NULL,line_number INTEGER NOT NULL,page INTEGER,text TEXT NOT NULL,locator TEXT,bbox_json TEXT,coordinate_space TEXT,page_width REAL,page_height REAL,confidence REAL,FOREIGN KEY(document_id) REFERENCES documents(id));
          CREATE TABLE IF NOT EXISTS evidence_lines(owner_id TEXT NOT NULL,evidence_id TEXT PRIMARY KEY,document_id TEXT NOT NULL,line_id TEXT NOT NULL,FOREIGN KEY(evidence_id) REFERENCES evidence(id),FOREIGN KEY(document_id) REFERENCES documents(id),FOREIGN KEY(line_id) REFERENCES document_lines(id));
          CREATE TABLE IF NOT EXISTS source_documents(owner_id TEXT NOT NULL,source_id TEXT PRIMARY KEY,document_id TEXT NOT NULL,FOREIGN KEY(source_id) REFERENCES import_sources(id),FOREIGN KEY(document_id) REFERENCES documents(id));
          CREATE INDEX IF NOT EXISTS idx_document_lines_owner_doc ON document_lines(owner_id,document_id,line_number);
        ''')
        _record(connection,7,'document_line_evidence','original documents; normalized lines; evidence and source bindings')

    if 8 not in applied and {'facts','rules'}.issubset(tables):
        connection.executescript('''
          CREATE TABLE IF NOT EXISTS profile_versions(owner_id TEXT PRIMARY KEY,revision INTEGER NOT NULL,updated_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS rule_semantics(rule_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('scope','eligibility','action_trigger')),FOREIGN KEY(rule_id) REFERENCES rules(id));
        ''')
        _record(connection,8,'typed_profile_rule_semantics','profile revisions; rule scope eligibility action-trigger classification')

    if 9 not in applied and {'evidence','imports'}.issubset(tables):
        connection.executescript('''
          CREATE TABLE IF NOT EXISTS knowledge_documents(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,document_id TEXT NOT NULL,title TEXT NOT NULL,category TEXT NOT NULL,publisher TEXT NOT NULL,effective_date TEXT,status TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(owner_id,document_id),FOREIGN KEY(document_id) REFERENCES documents(id));
          CREATE TABLE IF NOT EXISTS knowledge_chunks(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,knowledge_id TEXT NOT NULL,chunk_index INTEGER NOT NULL,text TEXT NOT NULL,line_ids_json TEXT NOT NULL,page INTEGER,index_version TEXT NOT NULL,FOREIGN KEY(knowledge_id) REFERENCES knowledge_documents(id));
          CREATE INDEX IF NOT EXISTS idx_knowledge_owner ON knowledge_chunks(owner_id,knowledge_id);
          CREATE TABLE IF NOT EXISTS knowledge_evidence_sources(owner_id TEXT NOT NULL,evidence_id TEXT PRIMARY KEY,document_id TEXT NOT NULL,chunk_hash TEXT NOT NULL,FOREIGN KEY(evidence_id) REFERENCES evidence(id),FOREIGN KEY(document_id) REFERENCES documents(id));
        ''')
        _record(connection,9,'private_knowledge_corpus','owner-isolated imported knowledge documents; cited chunks')

    if 10 not in applied and {'evidence','imports'}.issubset(tables):
        connection.executescript('''
          CREATE TABLE IF NOT EXISTS document_privacy_findings(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,document_id TEXT NOT NULL,revision INTEGER NOT NULL,line_id TEXT NOT NULL,type TEXT NOT NULL,page INTEGER,bbox_json TEXT,masked_preview TEXT NOT NULL,FOREIGN KEY(document_id) REFERENCES documents(id));
          CREATE TABLE IF NOT EXISTS document_derivatives(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,document_id TEXT NOT NULL,revision INTEGER NOT NULL,mime TEXT NOT NULL,selected_ids_json TEXT NOT NULL,sha256 TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(document_id) REFERENCES documents(id));
        ''')
        _record(connection,10,'privacy_document_copies','coordinate findings without raw values; permanently redacted derivative files')

    if 11 not in applied and 'tasks' in tables:
        connection.executescript('''
          CREATE TABLE IF NOT EXISTS schedule_drafts(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,state_hash TEXT NOT NULL,result_json TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN ('pending','committed')),created_at TEXT NOT NULL,committed_at TEXT);
          CREATE INDEX IF NOT EXISTS idx_schedule_drafts_owner ON schedule_drafts(owner_id,created_at);
        ''')
        _record(connection,11,'atomic_schedule_drafts','immutable owner drafts; state checks; atomic idempotent commitment')

    if 12 not in applied and 'imports' in tables:
        connection.executescript('''
          CREATE TABLE IF NOT EXISTS analysis_review_versions(owner_id TEXT NOT NULL,case_id TEXT NOT NULL,revision INTEGER NOT NULL,candidate_json TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(owner_id,case_id,revision));
          CREATE TABLE IF NOT EXISTS import_case_sources(owner_id TEXT NOT NULL,import_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,evidence_ids_json TEXT NOT NULL,FOREIGN KEY(import_id) REFERENCES imports(id));
        ''')
        _record(connection,12,'analysis_history_retry_sources','immutable candidate versions; owner-authorized retry evidence bindings')

    if 13 not in applied and 'facts' in tables:
        connection.executescript('''
          CREATE TABLE IF NOT EXISTS fact_history(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,case_id TEXT,key TEXT NOT NULL,value_json TEXT NOT NULL,source TEXT NOT NULL,created_at TEXT NOT NULL,valid_until TEXT);
          CREATE TABLE IF NOT EXISTS fact_validity(fact_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,valid_until TEXT);
          INSERT OR IGNORE INTO fact_history SELECT id,owner_id,case_id,key,value_json,source,created_at,NULL FROM facts;
          CREATE INDEX IF NOT EXISTS idx_fact_history_owner ON fact_history(owner_id,created_at);
        ''')
        _record(connection,13,'fact_history_validity','retain fact assertions after replacement; explicit validity; expired UNKNOWN')

    if 14 not in applied and 'tasks' in tables:
        connection.executescript('''
          CREATE TABLE IF NOT EXISTS task_planning(task_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,splittable INTEGER NOT NULL,min_chunk_minutes INTEGER NOT NULL,max_chunk_minutes INTEGER NOT NULL,importance REAL NOT NULL,preference REAL NOT NULL,evidence_id TEXT NOT NULL,updated_at TEXT NOT NULL);
        ''')
        _record(connection,14,'task_planning_preferences','explicit user duration split limits importance preference; evidence assertions')

    if 15 not in applied and 'tasks' in tables:
        connection.executescript('''
          CREATE TABLE IF NOT EXISTS schedule_locks(item_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,locked INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS task_edge_evidence(edge_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,evidence_ids_json TEXT NOT NULL,source TEXT NOT NULL);
        ''')
        _record(connection,15,'schedule_locks_dependency_evidence','explicit schedule locks; cited dependency origins')

    if 16 not in applied and 'facts' in tables:
        connection.executescript('''
          CREATE TABLE IF NOT EXISTS profile_interests(owner_id TEXT PRIMARY KEY,categories_json TEXT NOT NULL,revision INTEGER NOT NULL,updated_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS case_interest_evidence(owner_id TEXT NOT NULL,case_id TEXT NOT NULL,revision INTEGER NOT NULL,evidence_id TEXT NOT NULL,PRIMARY KEY(owner_id,case_id));
        ''')
        _record(connection,16,'soft_interest_evidence','owner interest categories separate from hard AST; user assertion refs')

    if 17 not in applied and 'cases' in tables:
        connection.execute('CREATE TABLE IF NOT EXISTS case_attachment_documents(owner_id TEXT NOT NULL,case_id TEXT NOT NULL,document_id TEXT PRIMARY KEY,evidence_id TEXT NOT NULL)')
        _record(connection,17,'case_attachment_inventory','owner-scoped explicit attachments, including failed parse receipts')
    if 18 not in applied and 'cases' in tables:
        connection.execute('CREATE TABLE IF NOT EXISTS case_attachment_links(owner_id TEXT NOT NULL,case_id TEXT NOT NULL,url TEXT NOT NULL,title TEXT NOT NULL,evidence_id TEXT NOT NULL,PRIMARY KEY(owner_id,case_id,url))')
        _record(connection,18,'case_attachment_links','retain discovered links as evidence, never auto-fetch')
