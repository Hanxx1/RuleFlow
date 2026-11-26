import pytest

from app.auth import conn
from app.providers.vault import get_vault_content_provider
from helpers import account, client, head
from test_schedule_drafts import setup_case


@pytest.fixture
def standalone():
    # Only the isolated, empty test DB gets the pending nullable Task shape.
    with conn() as db:
        assert db.execute("SELECT count(*) FROM tasks").fetchone()[0] == 0
        schema = db.execute("SELECT sql FROM sqlite_master WHERE name='tasks'").fetchone()[0]
        indexes = db.execute("SELECT sql FROM sqlite_master WHERE tbl_name='tasks' AND type='index' AND sql IS NOT NULL").fetchall()
        assert "case_id TEXT NOT NULL" in schema
        db.execute("DROP TABLE tasks")
        db.execute(schema.replace("case_id TEXT NOT NULL", "case_id TEXT"))
        for index in indexes:
            db.execute(index[0])
    owner = account("owner@example.org")
    other = account("other@example.org")
    with conn() as db:
        for task, user in [("first", owner), ("second", owner), ("foreign", other)]:
            db.execute("""INSERT INTO tasks(id, owner_id, case_id, title, status, evidence_ids_json, created_at, updated_at)
                          VALUES(?,?,NULL,?,'todo','[]','now','now')""", (task, user["user"]["id"], task))
    return head(owner), head(other)


def upload(headers, **fields):
    response = client.post("/api/v1/vault/items", headers=headers, data={"consent":"true", **fields},
                           files={"file":("shared.txt", b"shared original", "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def listing(task):
    return f"/api/v1/tasks/{task}/vault/items"


def test_shared_original_and_single_unlink(standalone):
    headers, _ = standalone
    item = upload(headers)
    first, second = [listing(task) + "/" + item for task in ("first", "second")]
    for url in (first, first, second):
        assert client.put(url, headers=headers).status_code == 200
    assert client.patch("/api/v1/vault/items/" + item, headers=headers, json={"name":"renamed.txt"}).status_code == 200
    rows = client.get(listing("first"), headers=headers).json()["data"]
    assert len(rows) == 1 and rows[0]["content_url"] == first + "/content"
    for query, disposition in [("", "inline"), ("?download=true", "attachment")]:
        response = client.get(rows[0]["content_url"] + query, headers=headers)
        assert response.status_code == 200 and response.content == b"shared original"
        assert response.headers["content-disposition"].startswith(disposition + ";")
    for expected in (True, False):
        assert client.delete(first, headers=headers).json()["data"]["unlinked"] is expected
    assert client.get(listing("first"), headers=headers).json()["data"] == []
    assert client.get(first + "/content", headers=headers).status_code == 404
    for url in (second, "/api/v1/vault/items/" + item):
        assert client.get(url + "/content", headers=headers).content == b"shared original"
    with conn() as db:
        assert db.execute("SELECT count(*) FROM vault_items").fetchone()[0] == 1
        assert not db.execute("PRAGMA foreign_key_check").fetchall()


def test_auth_and_missing_content(standalone):
    headers, other = standalone
    item = upload(headers)
    url = listing("first") + "/" + item
    assert client.put(url, headers=headers).status_code == 200
    for method, path in [("GET", listing("first")), ("PUT", url), ("DELETE", url), ("GET", url+"/content")]:
        assert client.request(method, path).status_code == 401
        invalid = client.request(method, path, headers={"Authorization":"Bearer invalid"})
        assert invalid.status_code == 401 and invalid.json()["detail"] == "会话已过期"
        denied = client.request(method, path, headers=other)
        assert denied.status_code == 404 and denied.json()["detail"] == "资源不存在"
    for method, suffix in [("PUT",""), ("DELETE",""), ("GET","/content")]:
        denied = client.request(method, listing("foreign")+"/"+item+suffix, headers=other)
        assert denied.status_code == 404 and denied.json()["detail"] == "资源不存在"
    assert client.get(url+"/content", headers=headers).content == b"shared original"
    with conn() as db:
        row = db.execute("SELECT * FROM vault_items WHERE id=?", (item,)).fetchone()
    get_vault_content_provider().delete(row["owner_id"], row["content_provider"], row["content_key"])
    missing = client.get(url+"/content", headers=headers)
    assert missing.status_code == 404 and missing.json()["detail"] == "材料内容不存在"


def test_legacy_case_guard():
    user, case = setup_case("old-case@example.org")
    headers = head(user)
    task = client.get(f"/api/v1/cases/{case}/plan", headers=headers).json()["data"]["ordered_tasks"][0]["id"]
    item = upload(headers)
    url = listing(task) + "/" + item
    assert client.put(url, headers=headers).status_code == 422
    lib = "/api/v1/vault/items/" + item
    assert client.patch(lib, headers=headers, json={"case_ids":[case]}).status_code == 200
    assert client.put(url, headers=headers).status_code == 200
    assert client.get(url+"/content", headers=headers).content == b"shared original"
    assert client.delete(url, headers=headers).status_code == 200
    metadata = client.get(lib, headers=headers).json()["data"]
    assert metadata["case_ids"] == [case] and metadata["task_ids"] == []
