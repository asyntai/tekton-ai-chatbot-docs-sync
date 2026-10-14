#!/usr/bin/env python3
"""A stand-in for the Asyntai knowledge base API, run as a Pod in the cluster.

It answers the endpoints the task uses and keeps the entries in memory.
GET /__state returns every entry (with its text) and every call it received;
POST /__reset clears both. The e2e runner uses these two to check what the
task really did.
"""

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_KEY = "test-key-2f8a1c"
STATE = {"entries": {}, "calls": []}
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, code, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length).decode("utf-8") if length else ""

    def _record(self, method):
        with LOCK:
            STATE["calls"].append({
                "method": method,
                "path": self.path,
                "user_agent": self.headers.get("User-Agent", ""),
            })

    def _authorised(self):
        if self.headers.get("Authorization", "") != "Bearer " + API_KEY:
            self._send(401, {"success": False, "error": "Invalid API key"})
            return False
        return True

    def do_GET(self):
        if self.path == "/__state":
            with LOCK:
                self._send(200, {"entries": list(STATE["entries"].values()),
                                 "calls": list(STATE["calls"])})
            return
        self._record("GET")
        if not self._authorised():
            return
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/api/v1/knowledge":
            with LOCK:
                entries = [{k: v for k, v in e.items() if k != "content"}
                           for e in STATE["entries"].values()]
            self._send(200, {"success": True, "entries": entries})
            return
        if path.startswith("/api/v1/knowledge/"):
            with LOCK:
                entry = STATE["entries"].get(path.rsplit("/", 1)[-1])
            if not entry:
                self._send(404, {"success": False,
                                 "error": "Knowledge base entry not found"})
                return
            payload = dict(entry)
            payload.update({"success": True, "content_available": True})
            self._send(200, payload)
            return
        self._send(404, {"success": False, "error": "Not found"})

    def do_POST(self):
        if self.path == "/__reset":
            self._body()
            with LOCK:
                STATE["entries"].clear()
                STATE["calls"].clear()
            self._send(200, {"ok": True})
            return
        self._record("POST")
        raw = self._body()
        if not self._authorised():
            return
        if self.path.rstrip("/") != "/api/v1/knowledge/text":
            self._send(404, {"success": False, "error": "Not found"})
            return
        body = json.loads(raw or "{}")
        title = body.get("title") or ""
        content = body.get("content") or ""
        if not title or len(content) < 10:
            self._send(400, {"success": False, "error": "invalid entry"})
            return
        entry_id = str(uuid.uuid4())
        with LOCK:
            STATE["entries"][entry_id] = {
                "id": entry_id, "type": "text", "title": title,
                "content": content, "website_id": body.get("website_id"),
            }
        self._send(200, {"success": True, "id": entry_id, "title": title,
                         "chunks_created": 1})

    def do_DELETE(self):
        self._record("DELETE")
        if not self._authorised():
            return
        entry_id = self.path.rstrip("/").rsplit("/", 1)[-1]
        with LOCK:
            if entry_id not in STATE["entries"]:
                self._send(404, {"success": False,
                                 "error": "Knowledge base entry not found"})
                return
            del STATE["entries"][entry_id]
        self._send(200, {"success": True})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
