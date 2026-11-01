#!/usr/bin/env python3
"""Echo-OS KI-Agent.

* Steuert Kodi (JSON-RPC, lokal auf TCP 9090) und die Streaming-Apps
* Versteht natürliche Sprache über die Claude API (optional, mit API-Schlüssel)
* Erkennt neue Laufwerke und ordnet Filme/Serien/Musik automatisch der Bibliothek zu
* Überwacht Updates und Sicherheit und meldet Probleme auf dem Fernseher
* Web-Oberfläche: http://<echo-os>:8090
"""
import codecs
import configparser
import glob
import json
import logging
import os
import re
import secrets
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONF_PATH = os.environ.get("ECHOOS_AGENT_CONF", "/etc/echoos/agent.conf")
STATE_DIR = os.environ.get("ECHOOS_STATE", "/var/lib/echoos")
SERVICES_FILE = os.environ.get("ECHOOS_SERVICES", "/usr/share/echoos/services.json")
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
KODI_HOME = os.environ.get("ECHOOS_KODI_HOME", "/home/echoos/.kodi")
MEDIA_ROOT = os.environ.get("ECHOOS_MEDIA_ROOT", "/media")
MOUNTS_FILE = os.environ.get("ECHOOS_MOUNTS_FILE", "/proc/mounts")
KODI_PORT = int(os.environ.get("ECHOOS_KODI_PORT", "9090"))
CLAUDE_URL = os.environ.get("ECHOOS_CLAUDE_URL", "https://api.anthropic.com/v1/messages")

MOVIE_DIRS = {"filme", "film", "movies", "movie", "kino"}
SHOW_DIRS = {"serien", "serie", "tv shows", "tvshows", "tv", "series", "shows"}
MUSIC_DIRS = {"musik", "music", "audio"}
EXPECTED_PORTS = {22, 8090, 9090, 5353}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("echoos-agent")


# --------------------------------------------------------------------- Konfig
def load_conf():
    c = configparser.ConfigParser(interpolation=None)
    c.read(CONF_PATH)
    s = c["agent"] if c.has_section("agent") else {}
    return {
        "api_key": s.get("claude_api_key", "").strip(),
        "model": s.get("model", "claude-haiku-5-5").strip() or "claude-haiku-5-5",
        "workspace_id": s.get("workspace_id", "").strip(),
        "token": s.get("token", "").strip(),
        "port": int(s.get("port", "8090")),
        "auto_reboot": s.get("auto_reboot", "yes").strip().lower() in ("yes", "true", "1", "ja"),
    }


CONF = load_conf()
with open(SERVICES_FILE, encoding="utf-8") as fh:
    SERVICES = json.load(fh)
STATE_LOCK = threading.Lock()
STATE = {"updates": {}, "security": {}, "drives": [], "events": []}


def save_state():
    os.makedirs(STATE_DIR, exist_ok=True)
    with STATE_LOCK:
        data = json.dumps(STATE, ensure_ascii=False, indent=1)
    with open(os.path.join(STATE_DIR, "status.json"), "w", encoding="utf-8") as fh:
        fh.write(data)


def event(msg):
    log.info(msg)
    with STATE_LOCK:
        STATE["events"] = (STATE["events"] + [{"t": int(time.time()), "msg": msg}])[-50:]


def run(cmd, timeout=300, env=None):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, **(env or {})})
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as exc:  # noqa: BLE001
        return 1, str(exc)


# --------------------------------------------------------------------- Kodi
class Kodi:
    def __init__(self, host="127.0.0.1", port=9090):
        self.host, self.port = host, port
        self.lock = threading.Lock()
        self.req_id = 0

    def call(self, method, params=None, timeout=10):
        with self.lock:
            self.req_id += 1
            rid = self.req_id
            req = {"jsonrpc": "2.0", "id": rid, "method": method}
            if params is not None:
                req["params"] = params
            with socket.create_connection((self.host, self.port), timeout=timeout) as sock:
                sock.sendall(json.dumps(req).encode())
                decoder = json.JSONDecoder()
                utf8 = codecs.getincrementaldecoder("utf-8")()
                buf = ""
                deadline = time.time() + timeout
                while time.time() < deadline:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    buf += utf8.decode(chunk)
                    while buf:
                        buf = buf.lstrip()
                        try:
                            obj, idx = decoder.raw_decode(buf)
                        except ValueError:
                            break
                        buf = buf[idx:]
                        if isinstance(obj, dict) and obj.get("id") == rid:
                            if "error" in obj:
                                raise RuntimeError(obj["error"].get("message", "Kodi-Fehler"))
                            return obj.get("result")
        raise TimeoutError("Keine Antwort von Kodi")

    def alive(self):
        try:
            self.call("JSONRPC.Ping", timeout=2)
            return True
        except Exception:  # noqa: BLE001
            return False

    def notify(self, title, message, ms=8000):
        try:
            self.call("GUI.ShowNotification",
                      {"title": title, "message": message, "displaytime": ms})
        except Exception:  # noqa: BLE001
            pass

    def playing(self):
        try:
            return bool(self.call("Player.GetActivePlayers", timeout=3))
        except Exception:  # noqa: BLE001
            return False


kodi = Kodi(port=KODI_PORT)


def browser_active():
    code, out = run(["systemctl", "list-units", "--state=active", "--plain", "--no-legend",
                     "echoos-browser@*"], timeout=10)
    return code == 0 and bool(out.strip())


def ensure_kodi():
    if browser_active():
        run(["systemctl", "stop", "echoos-browser@*"], timeout=30)
    run(["systemctl", "start", "kodi.service"], timeout=30)
    for _ in range(30):
        if kodi.alive():
            return True
        time.sleep(1)
    return False


# --------------------------------------------------------------------- Werkzeuge
def tool_search_library(query):
    flt = lambda field: {"field": field, "operator": "contains", "value": query}  # noqa: E731
    out = []
    r = kodi.call("VideoLibrary.GetMovies", {"properties": ["title", "year", "playcount"],
                                             "filter": flt("title"), "limits": {"end": 15}})
    out += [{"type": "movie", "id": m["movieid"], "title": m["label"], "year": m.get("year"),
             "gesehen": bool(m.get("playcount"))} for m in (r or {}).get("movies", [])]
    r = kodi.call("VideoLibrary.GetTVShows", {"properties": ["title", "year"],
                                              "filter": flt("title"), "limits": {"end": 15}})
    out += [{"type": "tvshow", "id": s["tvshowid"], "title": s["label"], "year": s.get("year")}
            for s in (r or {}).get("tvshows", [])]
    r = kodi.call("AudioLibrary.GetAlbums", {"properties": ["artist", "year"],
                                             "filter": flt("album"), "limits": {"end": 10}})
    out += [{"type": "album", "id": a["albumid"], "title": a["label"],
             "artist": ", ".join(a.get("artist", []))} for a in (r or {}).get("albums", [])]
    r = kodi.call("AudioLibrary.GetArtists", {"filter": flt("artist"), "limits": {"end": 10}})
    out += [{"type": "artist", "id": a["artistid"], "title": a["label"]}
            for a in (r or {}).get("artists", [])]
    return {"treffer": out}


def tool_recent(kind="movies"):
    if kind == "episodes":
        r = kodi.call("VideoLibrary.GetRecentlyAddedEpisodes",
                      {"properties": ["showtitle", "season", "episode", "title"], "limits": {"end": 10}})
        return {"neu": [{"id": e["episodeid"], "serie": e["showtitle"],
                         "folge": f"S{e['season']:02d}E{e['episode']:02d}", "titel": e["title"]}
                        for e in (r or {}).get("episodes", [])]}
    r = kodi.call("VideoLibrary.GetRecentlyAddedMovies",
                  {"properties": ["title", "year"], "limits": {"end": 10}})
    return {"neu": [{"id": m["movieid"], "titel": m["label"], "jahr": m.get("year")}
                    for m in (r or {}).get("movies", [])]}


def tool_play(kind, item_id, season=None, episode=None):
    if not ensure_kodi():
        return {"fehler": "Kodi startet nicht"}
    item_id = int(item_id)
    if kind == "movie":
        item = {"movieid": item_id}
    elif kind == "episode":
        item = {"episodeid": item_id}
    elif kind == "album":
        item = {"albumid": item_id}
    elif kind == "artist":
        item = {"artistid": item_id}
    elif kind == "tvshow":
        r = kodi.call("VideoLibrary.GetEpisodes", {"tvshowid": item_id,
                      "properties": ["season", "episode", "playcount", "title"]})
        eps = sorted((r or {}).get("episodes", []), key=lambda e: (e["season"], e["episode"]))
        if not eps:
            return {"fehler": "Keine Folgen gefunden"}
        if season is not None:
            eps_s = [e for e in eps if e["season"] == int(season)
                     and (episode is None or e["episode"] == int(episode))]
            target = eps_s[0] if eps_s else None
        else:
            target = next((e for e in eps if not e.get("playcount")), eps[0])
        if not target:
            return {"fehler": "Diese Folge gibt es nicht"}
        item = {"episodeid": target["episodeid"]}
        kodi.call("Player.Open", {"item": item})
        return {"ok": True, "spielt": f"S{target['season']:02d}E{target['episode']:02d} {target['title']}"}
    else:
        return {"fehler": f"Unbekannter Typ {kind}"}
    kodi.call("Player.Open", {"item": item})
    return {"ok": True}


def tool_control(action, value=None):
    if action in ("volume", "lautstaerke"):
        kodi.call("Application.SetVolume", {"volume": max(0, min(100, int(value or 50)))})
        return {"ok": True}
    if action == "mute":
        kodi.call("Application.SetMute", {"mute": "toggle"})
        return {"ok": True}
    players = kodi.call("Player.GetActivePlayers") or []
    if not players:
        return {"fehler": "Es läuft gerade nichts"}
    pid = players[0]["playerid"]
    calls = {
        "play_pause": ("Player.PlayPause", {"playerid": pid}),
        "stop": ("Player.Stop", {"playerid": pid}),
        "next": ("Player.GoTo", {"playerid": pid, "to": "next"}),
        "previous": ("Player.GoTo", {"playerid": pid, "to": "previous"}),
        "forward": ("Player.Seek", {"playerid": pid, "value": {"seconds": int(value or 30)}}),
        "back": ("Player.Seek", {"playerid": pid, "value": {"seconds": -int(value or 10)}}),
        "subtitles": ("Player.SetSubtitle", {"playerid": pid, "subtitle": "next", "enable": True}),
        "audio_track": ("Player.SetAudioStream", {"playerid": pid, "stream": "next"}),
    }
    if action not in calls:
        return {"fehler": f"Unbekannte Aktion {action}"}
    method, params = calls[action]
    kodi.call(method, params)
    return {"ok": True}


def tool_now_playing():
    players = kodi.call("Player.GetActivePlayers") or []
    if not players:
        return {"spielt": None}
    pid = players[0]["playerid"]
    item = kodi.call("Player.GetItem", {"playerid": pid,
                     "properties": ["title", "showtitle", "season", "episode", "artist"]})
    prop = kodi.call("Player.GetProperties", {"playerid": pid,
                     "properties": ["percentage", "time", "totaltime", "speed"]})
    return {"spielt": item.get("item"), "status": prop}


def widevine_ready():
    code, out = run(["dpkg-query", "-W", "-f=${Status}", "libwidevinecdm0"], timeout=10)
    return code == 0 and "install ok installed" in out


def tool_launch_streaming(service):
    key = service.lower().replace(" ", "").replace("+", "plus")
    for svc in SERVICES:
        names = {svc["id"], svc["name"].lower().replace(" ", "").replace("+", "plus")}
        if key in names or any(key in n for n in names):
            if svc.get("drm") and not widevine_ready():
                return {"fehler": f"{svc['name']} braucht das DRM-Modul Widevine. Es wird nach dem ersten "
                                  "Start automatisch installiert – bitte in ein paar Minuten erneut versuchen."}
            kodi.notify(svc["name"], "Wird gestartet …", 3000)
            run(["systemctl", "start", "--no-block", f"echoos-browser@{svc['id']}.service"], timeout=15)
            event(f"Streaming gestartet: {svc['name']}")
            return {"ok": True, "dienst": svc["name"]}
    return {"fehler": "Dienst nicht gefunden", "verfuegbar": [s["name"] for s in SERVICES]}


def tool_back_to_kodi():
    return {"ok": ensure_kodi()}


def tool_scan_library():
    ensure_kodi()
    kodi.call("VideoLibrary.Scan", {"showdialogs": False})
    kodi.call("AudioLibrary.Scan", {"showdialogs": False})
    return {"ok": True, "info": "Bibliothek wird aktualisiert"}


def read_file(path, default=""):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return default


def tool_system_status():
    temp = read_file("/sys/class/thermal/thermal_zone0/temp", "0")
    _, throttled = run(["vcgencmd", "get_throttled"], timeout=5)
    _, df = run(["df", "-h", "--output=target,size,used,avail,pcent", "/", *current_mounts()], timeout=10)
    _, ip = run(["hostname", "-I"], timeout=5)
    os_rel = dict(re.findall(r'^(\w+)="?([^"\n]*)"?', read_file("/etc/os-release"), re.M))
    kodi_ver = None
    try:
        v = kodi.call("Application.GetProperties", {"properties": ["version"]}, timeout=3)["version"]
        kodi_ver = f"{v['major']}.{v['minor']}"
    except Exception:  # noqa: BLE001
        pass
    return {
        "system": os_rel.get("PRETTY_NAME"),
        "kernel": os.uname().release,
        "temperatur_c": round(int(temp) / 1000, 1),
        "drosselung": throttled,
        "uptime_h": round(float(read_file("/proc/uptime", "0 0").split()[0]) / 3600, 1),
        "ip": ip.split(),
        "kodi": kodi_ver,
        "streaming_app_aktiv": browser_active(),
        "speicher": df,
        "neustart_noetig": os.path.exists("/run/reboot-required"),
        "drm_widevine": widevine_ready(),
    }


def tool_check_updates():
    run(["apt-get", "update", "-q"], timeout=600)
    _, out = run(["apt", "list", "--upgradable"], timeout=120)
    pkgs = [ln.split("/")[0] for ln in out.splitlines() if "/" in ln and "Listing" not in ln]
    security = [ln.split("/")[0] for ln in out.splitlines() if "-security" in ln]
    res = {"zeit": int(time.time()), "anzahl": len(pkgs), "pakete": pkgs[:40],
           "sicherheit": security, "neustart_noetig": os.path.exists("/run/reboot-required")}
    with STATE_LOCK:
        STATE["updates"] = res
    save_state()
    return res


def tool_apply_updates(confirmed=False):
    if not confirmed:
        return {"fehler": "Bitte erst den Nutzer fragen und dann mit confirmed=true aufrufen"}
    if kodi.playing():
        return {"fehler": "Es läuft gerade etwas – Updates später installieren"}
    event("Updates werden installiert")
    code, out = run(["apt-get", "-y", "-q", "-o", "Dpkg::Options::=--force-confdef",
                     "-o", "Dpkg::Options::=--force-confold", "full-upgrade"],
                    timeout=3600, env={"DEBIAN_FRONTEND": "noninteractive"})
    run(["apt-get", "-y", "autoremove"], timeout=600, env={"DEBIAN_FRONTEND": "noninteractive"})
    res = tool_check_updates()
    event("Updates installiert" if code == 0 else "Updates fehlgeschlagen")
    return {"ok": code == 0, "rest": res["anzahl"], "neustart_noetig": res["neustart_noetig"],
            "log_ende": out[-1500:]}


def tool_security_report():
    warnings, info = [], {}
    _, ss = run(["ss", "-tlnH"], timeout=10)
    ports = set()
    for ln in ss.splitlines():
        parts = ln.split()
        if len(parts) >= 4:
            addr = parts[3]
            port = addr.rsplit(":", 1)[-1]
            local_only = addr.startswith(("127.", "[::1]", "::1"))
            if port.isdigit() and not local_only:
                ports.add(int(port))
    unexpected = sorted(ports - EXPECTED_PORTS)
    info["offene_ports"] = sorted(ports)
    if unexpected:
        warnings.append(f"Unerwartete offene Ports: {unexpected}")
    code, _ = run(["systemctl", "is-active", "nftables"], timeout=5)
    info["firewall"] = code == 0
    if code != 0:
        warnings.append("Firewall (nftables) ist nicht aktiv")
    _, failed = run(["journalctl", "-u", "ssh", "--since", "-24h", "--no-pager", "-q",
                     "--grep", "Failed password|Invalid user"], timeout=20)
    n_failed = len([ln for ln in failed.splitlines() if ln.strip()])
    info["ssh_fehlversuche_24h"] = n_failed
    if n_failed > 20:
        warnings.append(f"{n_failed} fehlgeschlagene SSH-Anmeldungen in 24 h")
    _, banned = run(["fail2ban-client", "status", "sshd"], timeout=10)
    m = re.search(r"Currently banned:\s*(\d+)", banned)
    info["gesperrte_ips"] = int(m.group(1)) if m else 0
    _, thr = run(["vcgencmd", "get_throttled"], timeout=5)
    m = re.search(r"0x([0-9a-fA-F]+)", thr)
    if m and int(m.group(1), 16) & 0x5:
        warnings.append("Unterspannung oder Drosselung – Netzteil prüfen")
    temp = int(read_file("/sys/class/thermal/thermal_zone0/temp", "0")) / 1000
    if temp > 80:
        warnings.append(f"Hohe Temperatur: {temp:.0f} °C")
    for dev in sorted(glob.glob("/dev/sd?") + glob.glob("/dev/nvme?n1")):
        code, out = run(["smartctl", "-H", dev], timeout=30)
        if "FAILED" in out or "FAILING" in out:
            warnings.append(f"Festplatte {dev} meldet SMART-Fehler – Daten sichern!")
    _, root = run(["df", "--output=pcent", "/"], timeout=5)
    m = re.search(r"(\d+)%", root)
    if m and int(m.group(1)) > 90:
        warnings.append(f"Systemspeicher zu {m.group(1)} % voll")
    pw = read_file("/etc/ssh/sshd_config.d/10-echoos.conf")
    info["ssh_passwortlogin"] = "PasswordAuthentication no" not in pw and os.path.exists("/run/sshd.pid")
    res = {"zeit": int(time.time()), "warnungen": warnings, **info}
    with STATE_LOCK:
        STATE["security"] = res
    save_state()
    return res


def tool_reboot(confirmed=False):
    if not confirmed:
        return {"fehler": "Bitte erst den Nutzer fragen"}
    if kodi.playing():
        return {"fehler": "Es läuft gerade etwas"}
    event("Neustart durch Agent")
    threading.Timer(3, lambda: run(["systemctl", "reboot"])).start()
    return {"ok": True}


TOOLS = {
    "search_library": (tool_search_library, "Durchsucht die Kodi-Bibliothek (Filme, Serien, Alben, Interpreten).",
                       {"query": {"type": "string"}}, ["query"]),
    "recently_added": (tool_recent, "Zuletzt hinzugefügte Filme oder Serienfolgen.",
                       {"kind": {"type": "string", "enum": ["movies", "episodes"]}}, []),
    "play": (tool_play, "Spielt ein Element ab. Bei tvshow ohne Staffel die nächste ungesehene Folge.",
             {"kind": {"type": "string", "enum": ["movie", "tvshow", "episode", "album", "artist"]},
              "item_id": {"type": "integer"}, "season": {"type": "integer"},
              "episode": {"type": "integer"}}, ["kind", "item_id"]),
    "control": (tool_control, "Wiedergabe steuern.",
                {"action": {"type": "string", "enum": ["play_pause", "stop", "next", "previous",
                                                       "forward", "back", "volume", "mute",
                                                       "subtitles", "audio_track"]},
                 "value": {"type": "integer", "description": "Sekunden oder Lautstärke 0-100"}},
                ["action"]),
    "now_playing": (tool_now_playing, "Was läuft gerade?", {}, []),
    "launch_streaming": (tool_launch_streaming, "Startet eine Streaming-App (z. B. Netflix, Disney+, ZDF).",
                         {"service": {"type": "string"}}, ["service"]),
    "back_to_kodi": (tool_back_to_kodi, "Schließt die Streaming-App und zeigt wieder Kodi.", {}, []),
    "scan_library": (tool_scan_library, "Bibliothek nach neuen Dateien durchsuchen.", {}, []),
    "system_status": (tool_system_status, "Systemzustand: Temperatur, Speicher, Laufwerke, Versionen.", {}, []),
    "check_updates": (tool_check_updates, "Prüft auf verfügbare Updates.", {}, []),
    "apply_updates": (tool_apply_updates, "Installiert alle Updates. Nur nach ausdrücklicher Zustimmung.",
                      {"confirmed": {"type": "boolean"}}, ["confirmed"]),
    "security_report": (tool_security_report, "Sicherheitsprüfung: Ports, Firewall, Logins, Festplatten.", {}, []),
    "reboot": (tool_reboot, "Startet das System neu. Nur nach ausdrücklicher Zustimmung.",
               {"confirmed": {"type": "boolean"}}, ["confirmed"]),
}

TOOL_SPECS = [{"name": n, "description": d,
               "input_schema": {"type": "object", "properties": p, "required": r}}
              for n, (_, d, p, r) in TOOLS.items()]

SYSTEM_PROMPT = (
    "Du bist ECHO, der KI-Agent von Echo-OS, einem Media-Center auf einem Raspberry Pi am Fernseher. "
    "Du steuerst Kodi und die Streaming-Apps und kümmerst dich um Updates und Sicherheit. "
    "Antworte kurz, freundlich und auf Deutsch. Nutze die Werkzeuge, statt zu raten. "
    "Wenn jemand etwas sehen will, suche es zuerst in der Bibliothek; gibt es dort nichts, "
    "schlage passende Streaming-Apps vor. Updates installieren und Neustarts nur nach "
    "ausdrücklicher Zustimmung im Chat. Verfügbare Streaming-Apps: "
    + ", ".join(s["name"] for s in SERVICES) + "."
)


def execute_tool(name, args):
    fn = TOOLS.get(name, (None,))[0]
    if not fn:
        return {"fehler": "Unbekanntes Werkzeug"}
    try:
        return fn(**(args or {}))
    except Exception as exc:  # noqa: BLE001
        log.exception("Werkzeug %s", name)
        return {"fehler": str(exc)}


# --------------------------------------------------------------------- Claude
CHAT_LOCK = threading.Lock()
HISTORY = []


def claude_request(messages):
    body = {"model": CONF["model"], "max_tokens": 1024, "system": SYSTEM_PROMPT,
            "tools": TOOL_SPECS, "messages": messages}
    req = urllib.request.Request(
        CLAUDE_URL, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {CONF['api_key']}", "anthropic-version": "2023-06-01",
                 "content-type": "application/json",
                 # Nur nötig, wenn der Schlüssel keinem Workspace zugeordnet ist
                 **({"anthropic-workspace-id": CONF["workspace_id"]} if CONF["workspace_id"] else {})})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def trim_history():
    while len(HISTORY) > 24:
        HISTORY.pop(0)
        # Nur an einer echten Nutzer-Nachricht beginnen (keine verwaisten tool_results)
        while HISTORY and not (HISTORY[0]["role"] == "user" and isinstance(HISTORY[0]["content"], str)):
            HISTORY.pop(0)


def chat_llm(text):
    with CHAT_LOCK:
        HISTORY.append({"role": "user", "content": text})
        actions = []
        for _ in range(8):
            resp = claude_request(HISTORY)
            content = resp.get("content", [])
            HISTORY.append({"role": "assistant", "content": content})
            if resp.get("stop_reason") != "tool_use":
                trim_history()
                reply = "".join(b.get("text", "") for b in content if b.get("type") == "text")
                return reply.strip() or "Erledigt.", actions
            results = []
            for block in content:
                if block.get("type") == "tool_use":
                    actions.append(block["name"])
                    out = execute_tool(block["name"], block.get("input"))
                    results.append({"type": "tool_result", "tool_use_id": block["id"],
                                    "content": json.dumps(out, ensure_ascii=False, default=str)[:8000]})
            HISTORY.append({"role": "user", "content": results})
        trim_history()
        return "Das hat zu viele Schritte gebraucht – bitte genauer formulieren.", actions


SIMPLE_COMMANDS = [
    (r"\b(pause|weiter|play)\b", lambda m: tool_control("play_pause")),
    (r"\b(stopp?|beenden)\b", lambda m: tool_control("stop")),
    (r"\bnächste\b", lambda m: tool_control("next")),
    (r"\blauter\b", lambda m: tool_control("volume", 80)),
    (r"\bleiser\b", lambda m: tool_control("volume", 30)),
    (r"\b(zurück zu kodi|kodi)\b", lambda m: tool_back_to_kodi()),
    (r"\bupdates?\b", lambda m: tool_check_updates()),
    (r"\bsicherheit\b", lambda m: tool_security_report()),
    (r"\bstatus\b", lambda m: tool_system_status()),
    (r"\b(scan|bibliothek)\b", lambda m: tool_scan_library()),
    (r"(?:starte?|öffne)\s+(.+)", lambda m: tool_launch_streaming(m.group(1))),
]


def chat_simple(text):
    t = text.lower().strip()
    for pattern, fn in SIMPLE_COMMANDS:
        m = re.search(pattern, t)
        if m:
            return json.dumps(fn(m), ensure_ascii=False, indent=1, default=str), []
    for svc in SERVICES:
        if svc["name"].lower() in t or svc["id"] in t:
            return json.dumps(tool_launch_streaming(svc["id"]), ensure_ascii=False), []
    return ("Ohne Claude-API-Schlüssel verstehe ich nur einfache Befehle: Pause, Stopp, lauter, "
            "leiser, Status, Updates, Sicherheit, Bibliothek, 'starte Netflix' …"), []


def chat(text):
    if CONF["api_key"]:
        try:
            return chat_llm(text)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            log.warning("Claude API: %s %s", exc.code, detail)
            reply, acts = chat_simple(text)
            return f"(Claude API nicht erreichbar: {exc.code}) {reply}", acts
        except Exception as exc:  # noqa: BLE001
            log.warning("Claude API: %s", exc)
            reply, acts = chat_simple(text)
            return f"(offline) {reply}", acts
    return chat_simple(text)


# --------------------------------------------------------------------- Laufwerke
def current_mounts():
    mounts = []
    for ln in read_file(MOUNTS_FILE).splitlines():
        parts = ln.split()
        if len(parts) > 2:
            mp = parts[1].encode().decode("unicode_escape")
            if mp.startswith(MEDIA_ROOT + "/"):
                mounts.append(mp)
    return sorted(mounts)


def video_db():
    dbs = glob.glob(os.path.join(KODI_HOME, "userdata/Database/MyVideos*.db"))
    dbs.sort(key=lambda p: int(re.findall(r"\d+", os.path.basename(p))[0]))
    return dbs[-1] if dbs else None


def set_video_content(path, content):
    """Weist einem Ordner Inhaltstyp + Scraper zu (wie 'Inhalt festlegen' in Kodi)."""
    db = video_db()
    if not db:
        return False
    path = path.rstrip("/") + "/"
    scraper = {"movies": "metadata.themoviedb.org.python",
               "tvshows": "metadata.tvshows.themoviedb.org.python"}[content]
    recursive = 2147483647 if content == "movies" else 0
    try:
        con = sqlite3.connect(db, timeout=15)
        with con:
            row = con.execute("SELECT idPath, strContent FROM path WHERE strPath=?", (path,)).fetchone()
            if row and row[1]:
                return True  # Nutzer hat selbst etwas festgelegt – nicht überschreiben
            if row:
                con.execute("UPDATE path SET strContent=?, strScraper=?, scanRecursive=?, "
                            "useFolderNames=0, noUpdate=0, exclude=0 WHERE idPath=?",
                            (content, scraper, recursive, row[0]))
            else:
                con.execute("INSERT INTO path (strPath, strContent, strScraper, scanRecursive, "
                            "useFolderNames, noUpdate, exclude) VALUES (?,?,?,?,0,0,0)",
                            (path, content, scraper, recursive))
        con.close()
        return True
    except sqlite3.Error as exc:
        log.warning("Bibliothek konnte %s nicht zuordnen: %s", path, exc)
        return False


def register_drive(mount, announce=True):
    found = []
    try:
        entries = [e for e in os.scandir(mount) if e.is_dir()]
    except OSError:
        return
    for entry in entries:
        name = entry.name.lower().strip()
        if name in MOVIE_DIRS and set_video_content(entry.path, "movies"):
            found.append(("video", entry.path, "Filme"))
        elif name in SHOW_DIRS and set_video_content(entry.path, "tvshows"):
            found.append(("video", entry.path, "Serien"))
        elif name in MUSIC_DIRS:
            found.append(("audio", entry.path, "Musik"))
    label = os.path.basename(mount)
    if announce:
        kinds = ", ".join(sorted({f[2] for f in found})) or "keine Filme/Serien/Musik-Ordner"
        kodi.notify("Laufwerk erkannt", f"{label}: {kinds}")
        event(f"Laufwerk {label} erkannt ({kinds})")
    for kind, path, _ in found:
        try:
            method = "VideoLibrary.Scan" if kind == "video" else "AudioLibrary.Scan"
            kodi.call(method, {"directory": path.rstrip("/") + "/", "showdialogs": False})
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------- Überwachung
def monitor():
    known, first = set(), True
    last_sec = last_upd = 0
    shown_token = False
    while True:
        try:
            if not shown_token and kodi.alive():
                # Kodi deaktiviert neu gefundene Addons – unser Streaming-Addon freischalten
                try:
                    kodi.call("Addons.SetAddonEnabled",
                              {"addonid": "plugin.program.echoos.streaming", "enabled": True})
                except Exception:  # noqa: BLE001
                    pass
                shown_token = announce_access()
            mounts = set(current_mounts())
            for m in sorted(mounts - known):
                if kodi.alive():
                    register_drive(m, announce=not first)
                else:
                    continue  # später nochmal versuchen
                known.add(m)
            for m in sorted(known - mounts):
                kodi.notify("Laufwerk entfernt", os.path.basename(m), 5000)
                event(f"Laufwerk {os.path.basename(m)} entfernt")
                known.discard(m)
            with STATE_LOCK:
                STATE["drives"] = sorted(known)
            first = False

            now = time.time()
            if now - last_sec > 3600:
                last_sec = now
                rep = tool_security_report()
                if rep["warnungen"]:
                    kodi.notify("Sicherheit", rep["warnungen"][0], 12000)
                    event("Sicherheitswarnung: " + "; ".join(rep["warnungen"]))
            if now - last_upd > 6 * 3600:
                last_upd = now
                upd = tool_check_updates()
                if upd["sicherheit"]:
                    event(f"{len(upd['sicherheit'])} Sicherheitsupdates offen (werden automatisch installiert)")
                if upd["neustart_noetig"]:
                    kodi.notify("Echo-OS", "Neustart für Updates nötig – erfolgt nachts automatisch", 10000)
            lt = time.localtime()
            if (CONF["auto_reboot"] and lt.tm_hour == 4 and lt.tm_min < 10
                    and os.path.exists("/run/reboot-required") and not kodi.playing()
                    and not browser_active() and read_uptime() > 3600):
                event("Automatischer Neustart nach Updates")
                run(["systemctl", "reboot"])
        except Exception:  # noqa: BLE001
            log.exception("Überwachung")
        time.sleep(10)


def read_uptime():
    return float(read_file("/proc/uptime", "0 0").split()[0])


def announce_access():
    marker = os.path.join(STATE_DIR, "access_shown")
    count = int(read_file(marker, "0") or 0)
    if count >= 3:
        return True
    _, ip = run(["hostname", "-I"], timeout=5)
    ip = (ip.split() or ["echo-os.local"])[0]
    kodi.notify("ECHO KI-Agent", f"http://{ip}:{CONF['port']}  –  Code: {CONF['token']}", 20000)
    with open(marker, "w") as fh:
        fh.write(str(count + 1))
    return True


# --------------------------------------------------------------------- Web
ACTIONS = {
    "back_to_kodi": lambda p: tool_back_to_kodi(),
    "check_updates": lambda p: tool_check_updates(),
    "apply_updates": lambda p: tool_apply_updates(confirmed=True),
    "security": lambda p: tool_security_report(),
    "scan": lambda p: tool_scan_library(),
    "reboot": lambda p: tool_reboot(confirmed=True),
    "launch": lambda p: tool_launch_streaming(str(p.get("service", ""))),
    "control": lambda p: tool_control(str(p.get("action", "")), p.get("value")),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "EchoAgent/1.0"
    failed = {}

    def log_message(self, fmt, *args):  # leiser
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self):
        ip = self.client_address[0]
        fails = Handler.failed.get(ip, (0, 0))
        if fails[0] >= 10 and time.time() - fails[1] < 600:
            return False
        token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if CONF["token"] and secrets.compare_digest(token, CONF["token"]):
            Handler.failed.pop(ip, None)
            return True
        Handler.failed[ip] = (fails[0] + 1, time.time())
        return False

    def _body(self):
        length = min(int(self.headers.get("Content-Length", 0) or 0), 65536)
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return {}

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(WEB_DIR, "index.html"), "rb") as fh:
                return self._send(200, fh.read(), "text/html")
        if self.path == "/api/services":
            return self._send(200, [{"id": s["id"], "name": s["name"], "color": s.get("color")}
                                    for s in SERVICES])
        if self.path == "/api/status":
            if not self._authorized():
                return self._send(401, {"fehler": "Code falsch"})
            with STATE_LOCK:
                state = json.loads(json.dumps(STATE, default=str))
            try:
                state["system"] = tool_system_status()
                state["now_playing"] = tool_now_playing() if kodi.alive() else None
            except Exception as exc:  # noqa: BLE001
                state["fehler"] = str(exc)
            state["ki"] = bool(CONF["api_key"])
            return self._send(200, state)
        return self._send(404, {"fehler": "nicht gefunden"})

    last_show = 0.0

    def do_POST(self):
        if self.path == "/api/show-code":
            # Zeigt den Code nur auf dem Fernseher an – wer ihn lesen kann, sitzt davor.
            now = time.time()
            if now - Handler.last_show < 30:
                return self._send(429, {"fehler": "Bitte 30 Sekunden warten"})
            Handler.last_show = now
            _, ip = run(["hostname", "-I"], timeout=5)
            ip = (ip.split() or ["echo-os.local"])[0]
            kodi.notify("ECHO KI-Agent", f"http://{ip}:{CONF['port']}  –  Code: {CONF['token']}", 20000)
            return self._send(200, {"ok": True})
        if not self._authorized():
            return self._send(401, {"fehler": "Code falsch"})
        body = self._body()
        if self.path == "/api/chat":
            text = str(body.get("message", ""))[:2000].strip()
            if not text:
                return self._send(400, {"fehler": "leer"})
            reply, actions = chat(text)
            return self._send(200, {"reply": reply, "actions": actions})
        if self.path == "/api/action":
            fn = ACTIONS.get(body.get("action"))
            if not fn:
                return self._send(400, {"fehler": "unbekannte Aktion"})
            return self._send(200, execute_wrapped(fn, body))
        return self._send(404, {"fehler": "nicht gefunden"})


def execute_wrapped(fn, body):
    try:
        return fn(body)
    except Exception as exc:  # noqa: BLE001
        return {"fehler": str(exc)}


def main():
    os.makedirs(STATE_DIR, exist_ok=True)
    if not CONF["token"]:
        log.warning("Kein Zugangscode in %s – Web-API gesperrt", CONF_PATH)
    threading.Thread(target=monitor, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", CONF["port"]), Handler)
    log.info("Echo-Agent läuft auf Port %s (KI: %s)", CONF["port"], "an" if CONF["api_key"] else "aus")
    server.serve_forever()


if __name__ == "__main__":
    main()
