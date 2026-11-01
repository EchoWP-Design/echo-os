#!/usr/bin/env python3
"""Simulierte Claude-API: prüft den Tool-Use-Ablauf des Agenten ohne echten API-Schlüssel.
Antwortet wie die echte Messages-API: erst Werkzeugaufrufe, dann eine Textantwort."""
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert self.headers["Authorization"] == "Bearer test-key"
        assert body["tools"] and body["system"]
        msgs = body["messages"]
        last = msgs[-1]["content"]
        def tool(id_, name, inp):
            return {"stop_reason": "tool_use", "content": [{"type": "tool_use", "id": id_, "name": name, "input": inp}]}
        if isinstance(last, str):
            q = last.lower()
            if "dark" in q:
                out = tool("t1", "search_library", {"query": "Dark"})
            elif "updates" in q:
                out = tool("t3", "check_updates", {})
            else:
                out = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Alles klar."}]}
        else:
            res = json.loads(last[0]["content"])
            tid = last[0]["tool_use_id"]
            if tid == "t1":
                show = next(t for t in res["treffer"] if t["type"] == "tvshow")
                out = tool("t2", "play", {"kind": "tvshow", "item_id": show["id"]})
            elif tid == "t2":
                out = {"stop_reason": "end_turn", "content": [{"type": "text",
                       "text": f"Läuft: Dark – {res.get('spielt')}. Viel Spaß!"}]}
            else:
                out = {"stop_reason": "end_turn", "content": [{"type": "text",
                       "text": f"Es gibt {res['anzahl']} Updates, davon {len(res['sicherheit'])} Sicherheitsupdate(s): {', '.join(res['sicherheit'])}. Soll ich sie installieren?"}]}
        data = json.dumps({"id": "msg_test", "type": "message", "role": "assistant", **out}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
