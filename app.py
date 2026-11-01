from __future__ import annotations
import json
import re
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
DATA_FILE = DATA_DIR / "keepsakes.json"

OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "gemma3:4b"
HOST = "127.0.0.1"
PORT = 8765
MAX_BODY = 1_000_000


class AppError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_records() -> list[dict[str, Any]]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        return []
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def write_records(records: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = DATA_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(DATA_FILE)


def clean_text(value: Any, field: str, limit: int, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise AppError(f"The {field} field must be text.")
    value = value.strip()
    if required and not value:
        raise AppError(f"Please add {field.lower()} before continuing.")
    if len(value) > limit:
        raise AppError(f"The {field.lower()} field is too long (maximum {limit} characters).")
    return value


def validate_memory(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "name": clean_text(payload.get("name"), "Name", 100, True),
        "relationship": clean_text(payload.get("relationship"), "Relationship", 100),
        "memory": clean_text(payload.get("memory"), "Memory", 7000, True),
        "details": clean_text(payload.get("details"), "Beloved details", 4000),
        "words": clean_text(payload.get("words"), "Words and sayings", 2000),
    }


def ollama_json(path: str, payload: dict[str, Any] | None = None, timeout: float = 3.0) -> dict[str, Any]:
    url = f"{OLLAMA_URL}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="GET" if data is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise AppError(f"Ollama returned an error: {detail or exc.reason}", 502) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AppError("Ollama is not reachable. Start Ollama, then try again. Your memories remain on this device.", 503) from exc
    except json.JSONDecodeError as exc:
        raise AppError("Ollama returned an unreadable response. Please try again.", 502) from exc


def model_health() -> dict[str, Any]:
    try:
        data = ollama_json("/api/tags", timeout=1.5)
        models = [m.get("name", "") for m in data.get("models", []) if isinstance(m, dict)]
        present = any(name == OLLAMA_MODEL or name.split(":", 1)[0] == OLLAMA_MODEL.split(":", 1)[0] and ":" not in OLLAMA_MODEL for name in models)
        return {"connected": True, "model": OLLAMA_MODEL, "model_present": present, "models": models}
    except AppError:
        return {"connected": False, "model": OLLAMA_MODEL, "model_present": False, "models": []}


def generate_remembrance(memory: dict[str, str]) -> dict[str, str]:
    system = (
        "You are Afterlight, a careful remembrance-writing assistant for a private digital ofrenda. "
        "Help people preserve real memories with warmth, dignity, and emotional restraint. "
        "Never claim to contact, channel, or speak for a deceased person. Never impersonate them. "
        "Do not invent dates, places, events, biographical facts, beliefs, or personality traits. "
        "Use only the details provided; you may use gentle sensory language, but do not present imagined details as facts. "
        "Many memories may come from Indian family life and may include regional-language words, kinship terms, food, "
        "festivals, journeys, neighbourhoods, prayers, or everyday routines. Preserve the words and spellings the user "
        "provides (for example, Nani, Dadaji, Ajji, Paati, Amma, Appa, chai, or saaptiya) instead of flattening them "
        "into generic English. When the user writes in English, Hindi, Hinglish, or a regional-language mix, mirror that "
        "choice naturally where practical; do not add extra local words just to sound Indian. Do not assume a person's "
        "religion, caste, language, region, or festival practices, and "
        "never add cultural details that the user did not provide. "
        "If information is sparse, write simply rather than filling gaps. Use natural, grounded language; avoid clichés and melodrama."
    )
    user = f"""Create a personal remembrance using only the supplied details.

Name: {memory['name']}
Relationship: {memory['relationship'] or 'Not specified'}
Memory: {memory['memory']}
Beloved things, rituals, foods, music, or places: {memory['details'] or 'Not specified'}
Words, sayings, or phrases remembered: {memory['words'] or 'Not specified'}

Return valid JSON with exactly these keys:
- title: a gentle title, maximum 8 words
- remembrance: 120–180 words in third person, grounded only in the supplied information
- lantern_note: one short, meaningful line (maximum 25 words) about what the memory keeps alive

Do not include markdown fences or any text outside the JSON object."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.68, "num_predict": 380, "num_ctx": 8192},
    }
    result = ollama_json("/api/chat", payload, timeout=240)
    content = result.get("message", {}).get("content", "").strip()
    if not content:
        raise AppError("The local model returned an empty remembrance. Please try once more.", 502)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {"title": f"In memory of {memory['name']}", "remembrance": content, "lantern_note": "A remembered moment can keep giving light."}
    title = clean_text(parsed.get("title"), "Title", 120) or f"In memory of {memory['name']}"
    remembrance = clean_text(parsed.get("remembrance"), "Remembrance", 10000, True)
    lantern_note = clean_text(parsed.get("lantern_note"), "Lantern note", 300) or "A remembered moment can keep giving light."
    return {"title": title, "remembrance": remembrance, "lantern_note": lantern_note}


class AfterlightHandler(BaseHTTPRequestHandler):
    server_version = "Afterlight/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep the local terminal quiet; no request data is logged.
        return

    def send_json(self, payload: dict[str, Any] | list[Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise AppError("Invalid request size.") from exc
        if length <= 0 or length > MAX_BODY:
            raise AppError("Request body is empty or too large.", 413)
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AppError("Request must contain valid JSON.") from exc
        if not isinstance(data, dict):
            raise AppError("Request must be a JSON object.")
        return data

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            health = model_health()
            health["privacy"] = "local"
            self.send_json(health)
            return
        if parsed.path == "/api/keepsakes":
            self.send_json(read_records())
            return
        if parsed.path == "/api/export":
            body = json.dumps({"app": "Afterlight", "version": 1, "exported_at": now_iso(), "keepsakes": read_records()}, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="afterlight-archive.json"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.serve_static(parsed.path)

    def serve_static(self, url_path: str) -> None:
        relative = unquote(url_path).lstrip("/") or "index.html"
        if ".." in Path(relative).parts:
            self.send_error(404)
            return
        target = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
            self.send_error(404)
            return
        if not target.is_file():
            self.send_error(404)
            return
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
        }.get(target.suffix.lower(), "application/octet-stream")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = self.read_json()
            if self.path == "/api/remember":
                memory = validate_memory(payload)
                health = model_health()
                if not health["connected"]:
                    raise AppError("Ollama is not running. Start Ollama and try again.", 503)
                if not health["model_present"]:
                    raise AppError(f"The model {OLLAMA_MODEL} is not installed yet. Run: ollama pull {OLLAMA_MODEL}", 503)
                output = generate_remembrance(memory)
                self.send_json({"memory": memory, "output": output, "model": OLLAMA_MODEL})
                return
            if self.path == "/api/keepsakes":
                memory = validate_memory(payload)
                output_supplied = "output" in payload
                output = payload.get("output")
                if output is not None:
                    if not isinstance(output, dict):
                        raise AppError("Generated remembrance must be an object.")
                    output = {
                        "title": clean_text(output.get("title"), "Title", 120),
                        "remembrance": clean_text(output.get("remembrance"), "Remembrance", 10000),
                        "lantern_note": clean_text(output.get("lantern_note"), "Lantern note", 300),
                    }
                records = read_records()
                record_id = clean_text(payload.get("id"), "ID", 80)
                timestamp = now_iso()
                existing = next((r for r in records if r.get("id") == record_id), None) if record_id else None
                stored_output = output if output_supplied else (existing or {}).get("output")
                record = {
                    "id": record_id if existing else str(uuid.uuid4()),
                    **memory,
                    "output": stored_output,
                    "created_at": (existing or {}).get("created_at", timestamp),
                    "updated_at": timestamp,
                }
                if existing:
                    records = [record if r.get("id") == record_id else r for r in records]
                else:
                    records.insert(0, record)
                write_records(records)
                self.send_json(record, 201 if not existing else 200)
                return
            raise AppError("Endpoint not found.", 404)
        except AppError as exc:
            self.send_json({"error": str(exc)}, exc.status)
        except Exception:
            self.send_json({"error": "Something went wrong while processing the request."}, 500)

    def do_DELETE(self) -> None:  # noqa: N802
        match = re.fullmatch(r"/api/keepsakes/([a-f0-9-]{36})", self.path)
        if not match:
            self.send_json({"error": "Keepsake not found."}, 404)
            return
        record_id = match.group(1)
        records = read_records()
        updated = [r for r in records if r.get("id") != record_id]
        if len(updated) == len(records):
            self.send_json({"error": "Keepsake not found."}, 404)
            return
        write_records(updated)
        self.send_json({"ok": True})


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), AfterlightHandler)
    print("\n  AFTERLIGHT — a private place for stories that stay")
    print(f"  Open http://{HOST}:{PORT} in your browser")
    print(f"  Model: {OLLAMA_MODEL} | Ollama: {OLLAMA_URL}")
    print("  Memories stay in this folder: " + str(DATA_DIR))
    print("  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAfterlight stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
