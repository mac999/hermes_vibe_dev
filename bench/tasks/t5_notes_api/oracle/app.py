from datetime import datetime, timezone

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

FIELDS = {"title", "body", "tags"}


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _validate(data, partial):
    out = {}
    if not partial or "title" in data:
        title = data.get("title")
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100:
            raise ApiError(400, "title must be a string of 1-100 characters")
        out["title"] = title.strip()
    if "body" in data:
        if not isinstance(data["body"], str):
            raise ApiError(400, "body must be a string")
        out["body"] = data["body"]
    if "tags" in data:
        tags = data["tags"]
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise ApiError(400, "tags must be a list of strings")
        out["tags"] = list(dict.fromkeys(tags))
    return out


def _json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "body must be a JSON object")
    return data


def _positive_int(name, default, maximum=None):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(400, f"{name} must be an integer") from None
    if value < 1 or (maximum and value > maximum):
        raise ApiError(400, f"{name} out of range")
    return value


def create_app():
    app = Flask(__name__)
    notes = {}
    counter = {"next": 1}

    @app.errorhandler(ApiError)
    def api_error(e):
        return jsonify(error=e.message), e.status

    @app.errorhandler(HTTPException)
    def http_error(e):
        return jsonify(error=e.description or e.name), e.code

    def get_or_404(note_id):
        if note_id not in notes:
            raise ApiError(404, "note not found")
        return notes[note_id]

    @app.post("/notes")
    def create():
        fields = _validate(_json_body(), partial=False)
        note_id = counter["next"]
        counter["next"] += 1
        note = {
            "id": note_id,
            "title": fields["title"],
            "body": fields.get("body", ""),
            "tags": fields.get("tags", []),
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        notes[note_id] = note
        return jsonify(note), 201, {"Location": f"/notes/{note_id}"}

    @app.get("/notes")
    def list_notes():
        page = _positive_int("page", 1)
        per_page = _positive_int("per_page", 10, 50)
        tag = request.args.get("tag")
        q = (request.args.get("q") or "").lower()
        items = [
            n for _, n in sorted(notes.items())
            if (tag is None or tag in n["tags"])
            and (not q or q in n["title"].lower() or q in n["body"].lower())
        ]
        start = (page - 1) * per_page
        return jsonify(items=items[start:start + per_page], page=page, per_page=per_page, total=len(items))

    @app.get("/notes/<int:note_id>")
    def get(note_id):
        return jsonify(get_or_404(note_id))

    @app.patch("/notes/<int:note_id>")
    def patch(note_id):
        note = get_or_404(note_id)
        data = _json_body()
        unknown = set(data) - FIELDS
        if unknown:
            raise ApiError(400, f"unknown fields: {', '.join(sorted(unknown))}")
        note.update(_validate(data, partial=True))
        return jsonify(note)

    @app.delete("/notes/<int:note_id>")
    def delete(note_id):
        get_or_404(note_id)
        del notes[note_id]
        return "", 204

    return app
