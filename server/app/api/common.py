"""Shared HTTP serialization and owner lookup; no router imports."""
from datetime import datetime, timezone
from fastapi import HTTPException
from ..auth import conn, envelope
from ..bootstrap import database

def stamp():return datetime.now(timezone.utc).isoformat()

def data(x,meta=None):return envelope(x,meta)

def owned(table,oid,uid):
 with conn() as c:r=c.execute(f'SELECT * FROM {table} WHERE id=? AND owner_id=?',(oid,uid)).fetchone()
 if not r:raise HTTPException(404,'资源不存在')
 return r

def schedule_item_json(row):
 item=dict(row);owner=item.pop('owner_id',None)
 with conn() as c:lock=c.execute('SELECT locked FROM schedule_locks WHERE item_id=? AND owner_id=?',(item['id'],owner)).fetchone()
 item['locked']=bool(lock and lock['locked']);return item
