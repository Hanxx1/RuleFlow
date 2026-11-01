"""Account routes: Argon2id passwords and opaque, rotating sessions."""
from __future__ import annotations
import hashlib, hmac, os, secrets, sqlite3
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from argon2 import PasswordHasher
from .migrations import apply_migrations
from .settings import SETTINGS

DB = SETTINGS.database_path
_memory_connection=None
PEPPER = os.getenv("REFRESH_TOKEN_PEPPER", "development-only-change-me")
ph, router = PasswordHasher(), APIRouter(tags=["auth"])
def now(): return datetime.now(timezone.utc).isoformat()
def digest(x): return hmac.new(PEPPER.encode(),x.encode(),hashlib.sha256).hexdigest()
def envelope(x,meta=None):
 result={"data":x,"request_id":secrets.token_hex(12),"meta":{"backend_mode":SETTINGS.backend_mode}}
 if meta:result["meta"].update(meta)
 return result
def conn():
 global _memory_connection
 if DB == ':memory:':
  if _memory_connection is None:
   _memory_connection=sqlite3.connect(':memory:',check_same_thread=False);_memory_connection.row_factory=sqlite3.Row;_memory_connection.execute('PRAGMA foreign_keys=ON')
  return _memory_connection
 DB.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA busy_timeout=30000"); c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=NORMAL"); return c
def init():
 with conn() as c: c.executescript("""
 CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,verified_at TEXT,created_at TEXT NOT NULL,deleted_at TEXT);
 CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,family_id TEXT NOT NULL,token_hash TEXT NOT NULL,expires_at TEXT NOT NULL,revoked_at TEXT,device_name TEXT,created_at TEXT NOT NULL,last_used_at TEXT,token_type TEXT NOT NULL DEFAULT 'refresh',FOREIGN KEY(user_id) REFERENCES users(id));
 CREATE TABLE IF NOT EXISTS verification_tokens(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,token_hash TEXT NOT NULL,purpose TEXT NOT NULL,expires_at TEXT NOT NULL,used_at TEXT,FOREIGN KEY(user_id) REFERENCES users(id));
 """); apply_migrations(c)
def issue(uid, token_type, device=None, family=None, minutes=None):
 if token_type not in {'access','refresh'}:raise ValueError('invalid session token type')
 raw,sid=secrets.token_urlsafe(48),secrets.token_hex(16); family=family or secrets.token_hex(16)
 expiry=datetime.now(timezone.utc)+timedelta(minutes=minutes or 30*24*60)
 with conn() as c:c.execute("INSERT INTO sessions(id,user_id,family_id,token_hash,expires_at,revoked_at,device_name,created_at,last_used_at,token_type) VALUES(?,?,?,?,?,?,?,?,?,?)",(sid,uid,family,digest(raw),expiry.isoformat(),None,device,now(),now(),token_type))
 return raw
def current_user(authorization: str|None=Header(default=None)):
 if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401,"需要登录")
 with conn() as c: u=c.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.token_type='access' AND s.revoked_at IS NULL AND s.expires_at>? AND u.deleted_at IS NULL",(digest(authorization[7:]),now())).fetchone()
 if not u: raise HTTPException(401,"会话已过期")
 return u
class Register(BaseModel): email:EmailStr; password:str=Field(min_length=12,max_length=128)
class EmailBody(BaseModel): email:EmailStr
class Login(Register): device_name:str|None=Field(default=None,max_length=128)
class Token(BaseModel): token:str=Field(min_length=20,max_length=512)
class Reset(Token): password:str=Field(min_length=12,max_length=128)
def verification(uid,purpose):
 raw,tid=secrets.token_urlsafe(32),secrets.token_hex(16); expiry=datetime.now(timezone.utc)+timedelta(minutes=15)
 with conn() as c:c.execute("INSERT INTO verification_tokens VALUES(?,?,?,?,?,NULL)",(tid,uid,digest(raw),purpose,expiry.isoformat()))
 return raw if os.getenv("APP_ENV","development")=="development" else None
def consume(raw,purpose):
 with conn() as c:
  row=c.execute("SELECT * FROM verification_tokens WHERE token_hash=? AND purpose=? AND used_at IS NULL AND expires_at>?",(digest(raw),purpose,now())).fetchone()
  if not row: raise HTTPException(400,"链接无效或已过期")
  c.execute("UPDATE verification_tokens SET used_at=? WHERE id=?",(now(),row["id"]))
 return row["user_id"]
@router.on_event("startup")
def startup(): init()
@router.post("/register")
def register(body:Register):
 init(); uid=secrets.token_hex(16)
 try:
  with conn() as c:c.execute("INSERT INTO users VALUES(?,?,?,?,?,NULL)",(uid,body.email.lower(),ph.hash(body.password),None,now()))
 except sqlite3.IntegrityError: raise HTTPException(409,"该邮箱已注册")
 return envelope({"id":uid,"email":body.email.lower(),"verification":"pending","development_verification_token":verification(uid,"verify")})
@router.post("/verify")
def verify(body:Token):
 uid=consume(body.token,"verify")
 with conn() as c:c.execute("UPDATE users SET verified_at=? WHERE id=?",(now(),uid))
 return envelope({"verified":True})
@router.post("/login")
def login(body:Login):
 with conn() as c:u=c.execute("SELECT * FROM users WHERE email=? AND deleted_at IS NULL",(body.email.lower(),)).fetchone()
 try: valid=bool(u) and ph.verify(u["password_hash"],body.password)
 except Exception: valid=False
 if not valid: raise HTTPException(401,"邮箱或密码错误")
 if not u["verified_at"]: raise HTTPException(403,"邮箱尚未验证")
 if SETTINGS.demo_mode:
  from .demo.bootstrap import bootstrap_owner
  bootstrap_owner(u["id"])
 family=secrets.token_hex(16)
 return envelope({"access_token":issue(u["id"],"access",body.device_name,family,minutes=15),"expires_in":900,"refresh_token":issue(u["id"],"refresh",body.device_name,family),"user":{"id":u["id"],"email":u["email"]}})
@router.post("/refresh")
def refresh(body:Token):
 with conn() as c:
  s=c.execute("SELECT * FROM sessions WHERE token_hash=? AND token_type='refresh'",(digest(body.token),)).fetchone()
  if not s or s["revoked_at"] or s["expires_at"]<=now(): raise HTTPException(401,"会话已过期")
  c.execute("UPDATE sessions SET revoked_at=? WHERE family_id=?",(now(),s["family_id"]))
 return envelope({"access_token":issue(s["user_id"],"access",s["device_name"],s["family_id"],minutes=15),"expires_in":900,"refresh_token":issue(s["user_id"],"refresh",s["device_name"],s["family_id"])})
@router.post("/password/reset-request")
def reset_request(body:EmailBody):
 with conn() as c:u=c.execute("SELECT id FROM users WHERE email=? AND deleted_at IS NULL",(body.email.lower(),)).fetchone()
 return envelope({"message":"如账号存在，将发送重置邮件。","development_reset_token":verification(u["id"],"reset") if u else None})
@router.post("/password/reset")
def reset(body:Reset):
 uid=consume(body.token,"reset")
 with conn() as c:c.execute("UPDATE users SET password_hash=? WHERE id=?",(ph.hash(body.password),uid));c.execute("UPDATE sessions SET revoked_at=? WHERE user_id=?",(now(),uid))
 return envelope({"reset":True})
@router.get("/sessions")
def sessions(user=Depends(current_user)):
 with conn() as c: rows=c.execute("SELECT id,device_name,created_at,last_used_at FROM sessions WHERE user_id=? AND token_type='refresh' AND revoked_at IS NULL",(user["id"],)).fetchall()
 return envelope([dict(r) for r in rows])
@router.delete("/sessions/{session_id}")
def revoke_session(session_id:str,user=Depends(current_user)):
 with conn() as c:
  session=c.execute("SELECT family_id FROM sessions WHERE id=? AND user_id=? AND token_type='refresh' AND revoked_at IS NULL",(session_id,user["id"])).fetchone()
  if not session:raise HTTPException(404,"会话不存在")
  c.execute("UPDATE sessions SET revoked_at=? WHERE family_id=? AND user_id=?",(now(),session["family_id"],user["id"]))
 return envelope({"id":session_id,"revoked":True})
@router.post("/logout")
def logout(body:Token):
 with conn() as c:
  session=c.execute("SELECT family_id FROM sessions WHERE token_hash=? AND token_type='refresh'",(digest(body.token),)).fetchone()
  if session:c.execute("UPDATE sessions SET revoked_at=? WHERE family_id=?",(now(),session["family_id"]))
 return envelope({"ok":True})
