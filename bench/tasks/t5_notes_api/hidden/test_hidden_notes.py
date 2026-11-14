import re

import pytest

from app import create_app


@pytest.fixture
def c():
    app = create_app()
    app.testing = True
    return app.test_client()


def mk(c, **kw):
    kw.setdefault("title", "t")
    return c.post("/notes", json=kw)


def test_create_and_get(c):
    r = mk(c, title="  Hello  ", body="world", tags=["a", "b", "a"])
    assert r.status_code == 201
    n = r.get_json()
    assert n["id"] == 1 and n["title"] == "Hello" and n["body"] == "world"
    assert n["tags"] == ["a", "b"]
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z", n["created_at"])
    assert r.headers["Location"].endswith("/notes/1")
    assert c.get("/notes/1").get_json() == n


def test_defaults(c):
    n = mk(c, title="x").get_json()
    assert n["body"] == "" and n["tags"] == []


@pytest.mark.parametrize("payload", [
    {}, {"title": ""}, {"title": "   "}, {"title": "x" * 101}, {"title": 5},
    {"title": "ok", "tags": "a"}, {"title": "ok", "tags": [1]}, {"title": "ok", "body": 3},
])
def test_create_validation(c, payload):
    r = c.post("/notes", json=payload)
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_title_100_ok(c):
    assert mk(c, title="x" * 100).status_code == 201


def test_non_json_body(c):
    r = c.post("/notes", data="title=x", content_type="text/plain")
    assert r.status_code == 400 and "error" in r.get_json()
    r = c.post("/notes", data="[1,2]", content_type="application/json")
    assert r.status_code == 400 and "error" in r.get_json()
    r = c.post("/notes", data="{bad", content_type="application/json")
    assert r.status_code == 400 and "error" in r.get_json()


def test_list_pagination(c):
    for i in range(23):
        mk(c, title=f"n{i}")
    r = c.get("/notes?page=3&per_page=10").get_json()
    assert r["total"] == 23 and r["page"] == 3 and r["per_page"] == 10
    assert [n["id"] for n in r["items"]] == [21, 22, 23]
    d = c.get("/notes").get_json()
    assert d["per_page"] == 10 and len(d["items"]) == 10 and d["items"][0]["id"] == 1
    assert c.get("/notes?page=9").get_json()["items"] == []


@pytest.mark.parametrize("qs", ["page=0", "page=x", "per_page=51", "per_page=0", "per_page=-1"])
def test_list_bad_params(c, qs):
    r = c.get(f"/notes?{qs}")
    assert r.status_code == 400 and "error" in r.get_json()


def test_list_filters(c):
    mk(c, title="Buy MILK", tags=["home"])
    mk(c, title="report", body="quarterly milk numbers", tags=["work"])
    mk(c, title="other", tags=["home", "x"])
    assert [n["id"] for n in c.get("/notes?tag=home").get_json()["items"]] == [1, 3]
    assert [n["id"] for n in c.get("/notes?q=milk").get_json()["items"]] == [1, 2]
    r = c.get("/notes?q=milk&tag=work").get_json()
    assert [n["id"] for n in r["items"]] == [2] and r["total"] == 1


def test_patch(c):
    mk(c, title="a", body="b", tags=["t"])
    r = c.patch("/notes/1", json={"body": "new"})
    assert r.status_code == 200
    n = r.get_json()
    assert n["title"] == "a" and n["body"] == "new" and n["tags"] == ["t"]
    assert c.patch("/notes/1", json={"title": ""}).status_code == 400
    assert c.patch("/notes/1", json={"color": "red"}).status_code == 400
    assert c.patch("/notes/99", json={"body": "x"}).status_code == 404
    assert c.get("/notes/1").get_json()["body"] == "new"


def test_delete_and_ids_not_reused(c):
    mk(c)
    mk(c)
    r = c.delete("/notes/2")
    assert r.status_code == 204 and r.data == b""
    assert c.delete("/notes/2").status_code == 404
    assert c.get("/notes/2").status_code == 404
    assert mk(c).get_json()["id"] == 3


def test_404_json(c):
    r = c.get("/notes/12345")
    assert r.status_code == 404 and "error" in r.get_json()
    r = c.get("/nope")
    assert r.status_code == 404 and "error" in r.get_json()


def test_apps_independent():
    a, b = create_app().test_client(), create_app().test_client()
    a.post("/notes", json={"title": "x"})
    assert b.get("/notes").get_json()["total"] == 0
