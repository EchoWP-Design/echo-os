#!/usr/bin/env python3
"""Simuliertes Kodi: beantwortet JSON-RPC über TCP wie Kodi auf Port 9090.

Enthält eine kleine Beispielbibliothek und protokolliert jeden Aufruf in
einer JSON-Lines-Datei, damit nachvollziehbar ist, was der Agent getan hat.
Aufruf: mock_kodi.py <port> <protokolldatei>
"""
import json
import socketserver
import sys
import threading

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 19090
LOG = sys.argv[2] if len(sys.argv) > 2 else "kodi_calls.jsonl"

MOVIES = [
    {"movieid": 1, "label": "Blade Runner", "year": 1982, "playcount": 1},
    {"movieid": 2, "label": "Tron", "year": 1982, "playcount": 0},
    {"movieid": 3, "label": "Ready Player One", "year": 2018, "playcount": 0},
    {"movieid": 4, "label": "Zurück in die Zukunft", "year": 1985, "playcount": 2},
]
SHOWS = [{"tvshowid": 10, "label": "Dark", "year": 2017},
         {"tvshowid": 11, "label": "Stranger Things", "year": 2016}]
EPISODES = {
    10: [{"episodeid": 100 + i, "season": 1 + i // 10, "episode": 1 + i % 10,
          "title": f"Folge {1 + i % 10}", "playcount": 1 if i < 3 else 0} for i in range(20)],
    11: [{"episodeid": 200 + i, "season": 1, "episode": 1 + i, "title": f"Kapitel {1 + i}",
          "playcount": 0} for i in range(8)],
}
ALBUMS = [{"albumid": 5, "label": "Synthwave Nights", "artist": ["Neon Drive"], "year": 2019}]
ARTISTS = [{"artistid": 7, "label": "Neon Drive"}]

STATE = {"player": None, "paused": False, "volume": 70, "lock": threading.Lock()}


def contains(items, flt, key="label"):
    if not flt:
        return items
    v = flt.get("value", "").lower()
    return [i for i in items if v in i[key].lower()]


def handle(method, p):
    p = p or {}
    if method == "JSONRPC.Ping":
        return "pong"
    if method == "GUI.ShowNotification":
        return "OK"
    if method == "Application.GetProperties":
        return {"version": {"major": 21, "minor": 2}, "volume": STATE["volume"]}
    if method == "Application.SetVolume":
        STATE["volume"] = p["volume"]
        return STATE["volume"]
    if method == "Application.SetMute":
        return True
    if method == "VideoLibrary.GetMovies":
        return {"movies": contains(MOVIES, p.get("filter"))}
    if method == "VideoLibrary.GetTVShows":
        return {"tvshows": contains(SHOWS, p.get("filter"))}
    if method == "VideoLibrary.GetEpisodes":
        return {"episodes": EPISODES.get(p["tvshowid"], [])}
    if method == "VideoLibrary.GetRecentlyAddedMovies":
        return {"movies": MOVIES[::-1]}
    if method == "VideoLibrary.GetRecentlyAddedEpisodes":
        eps = [dict(e, showtitle="Dark") for e in EPISODES[10][-3:]]
        return {"episodes": eps}
    if method == "AudioLibrary.GetAlbums":
        return {"albums": contains(ALBUMS, p.get("filter"))}
    if method == "AudioLibrary.GetArtists":
        return {"artists": contains(ARTISTS, p.get("filter"))}
    if method in ("VideoLibrary.Scan", "AudioLibrary.Scan", "Addons.SetAddonEnabled"):
        return "OK"
    if method == "Player.Open":
        item = p["item"]
        if "movieid" in item:
            m = next(m for m in MOVIES if m["movieid"] == item["movieid"])
            STATE["player"] = {"type": "movie", "title": m["label"], "label": m["label"]}
        elif "episodeid" in item:
            for sid, eps in EPISODES.items():
                for e in eps:
                    if e["episodeid"] == item["episodeid"]:
                        show = next(s for s in SHOWS if s["tvshowid"] == sid)
                        STATE["player"] = {"type": "episode", "title": e["title"], "label": e["title"],
                                           "showtitle": show["label"], "season": e["season"],
                                           "episode": e["episode"]}
        else:
            STATE["player"] = {"type": "song", "title": "Synthwave Nights", "label": "Synthwave Nights"}
        STATE["paused"] = False
        return "OK"
    if method == "Player.GetActivePlayers":
        return [{"playerid": 1, "type": "video"}] if STATE["player"] else []
    if method == "Player.GetItem":
        return {"item": STATE["player"]}
    if method == "Player.GetProperties":
        return {"percentage": 12.5, "speed": 0 if STATE["paused"] else 1,
                "time": {"hours": 0, "minutes": 6, "seconds": 2},
                "totaltime": {"hours": 0, "minutes": 52, "seconds": 0}}
    if method == "Player.PlayPause":
        STATE["paused"] = not STATE["paused"]
        return {"speed": 0 if STATE["paused"] else 1}
    if method == "Player.Stop":
        STATE["player"] = None
        return "OK"
    if method in ("Player.GoTo", "Player.Seek", "Player.SetSubtitle", "Player.SetAudioStream"):
        return "OK"
    raise KeyError(method)


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        data = b""
        dec = json.JSONDecoder()
        while True:
            chunk = self.request.recv(65536)
            if not chunk:
                return
            data += chunk
            try:
                req, _ = dec.raw_decode(data.decode())
            except ValueError:
                continue
            break
        with STATE["lock"]:
            try:
                result = handle(req["method"], req.get("params"))
                resp = {"jsonrpc": "2.0", "id": req.get("id"), "result": result}
            except KeyError:
                resp = {"jsonrpc": "2.0", "id": req.get("id"),
                        "error": {"code": -32601, "message": "Method not found."}}
            with open(LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"method": req["method"], "params": req.get("params")},
                                    ensure_ascii=False) + "\n")
        # Kodi schickt manchmal vorher Benachrichtigungen – das simulieren wir auch
        note = {"jsonrpc": "2.0", "method": "Other.Ping", "params": {"data": "ü"}}
        self.request.sendall((json.dumps(note) + json.dumps(resp, ensure_ascii=False)).encode())


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server(("127.0.0.1", PORT), Handler) as srv:
        print(f"Mock-Kodi auf Port {PORT}", flush=True)
        srv.serve_forever()
