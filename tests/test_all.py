#!/usr/bin/env python3
"""Echo-OS Funktionstests (laufen ohne Raspberry Pi).

Startet ein simuliertes Kodi, eine simulierte Claude-API und den echten
Echo-Agenten und prüft Bibliothekserkennung, Steuerung, Chat mit
Werkzeugaufrufen, Updates/Sicherheit, Web-API, Kodi-Addon, Kacheln und
Konfiguration. Ergebnis: tests/out/report.json + Protokolle.
"""
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FS = os.path.join(ROOT, "stage-echoos/00-echoos/files/rootfs")
OUT = os.path.join(HERE, "out")
SERVICES = os.path.join(FS, "usr/share/echoos/services.json")
AGENT = os.path.join(FS, "opt/echoos/agent/echoos_agent.py")
PY = sys.executable

RESULTS = []
PROCS = []


def check(name, cond, detail=""):
    RESULTS.append({"test": name, "ok": bool(cond), "detail": str(detail)[:400]})
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"  ({detail})" if detail and not cond else ""))
    return cond


def section(title):
    print(f"\n== {title}")
    RESULTS.append({"section": title})


def start(cmd, env=None, log=None):
    fh = open(log, "w") if log else subprocess.DEVNULL
    p = subprocess.Popen(cmd, env=env, stdout=fh, stderr=subprocess.STDOUT)
    PROCS.append(p)
    return p


def http(port, path, body=None, token=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def wait_port(port, timeout=15):
    import socket
    end = time.time() + timeout
    while time.time() < end:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            return True
        except OSError:
            time.sleep(0.2)
    return False


def kodi_calls(path):
    if not os.path.exists(path):
        return []
    return [json.loads(ln) for ln in open(path, encoding="utf-8") if ln.strip()]


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    work = tempfile.mkdtemp(prefix="echoos-test-")
    syslog = os.path.join(OUT, "system_commands.log")
    env = {**os.environ, "PATH": f"{HERE}/fakebin:{os.environ['PATH']}", "ECHOOS_TEST_LOG": syslog,
           "ECHOOS_SERVICES": SERVICES, "PIMEDIA_TILE_DIR": ""}

    # ------------------------------------------------------------ Kacheln
    section("Streaming-Kacheln und Kodi-Favoriten")
    tiles = os.path.join(OUT, "tiles")
    src = open(os.path.join(FS, "usr/local/lib/echoos/gen_tiles.py")).read()
    src = src.replace('"/usr/share/echoos/services.json"', repr(SERVICES))
    code = subprocess.run([PY, "-c", src], env={**env, "PIMEDIA_TILE_DIR": tiles, "ECHOOS_TILE_DIR": tiles},
                          capture_output=True, text=True)
    services = json.load(open(SERVICES))
    made = sorted(f for f in os.listdir(tiles)) if os.path.isdir(tiles) else []
    check("Für jede App eine Kachel erzeugt", len(made) == len(services) + 1, f"{len(made)} Dateien {code.stderr}")
    src = open(os.path.join(FS, "usr/local/lib/echoos/gen_favourites.py")).read()
    src = src.replace('"/usr/share/echoos/services.json"', repr(SERVICES))
    fav = subprocess.run([PY, "-c", src], capture_output=True, text=True).stdout
    open(os.path.join(OUT, "favourites.xml"), "w").write(fav)
    try:
        favs = ET.fromstring(fav).findall("favourite")
        check("favourites.xml ist gültiges XML", True)
        check(f"{len(services)} Favoriten mit Kachel und Startbefehl",
              len(favs) == len(services) and all("RunPlugin" in f.text and f.get("thumb") for f in favs))
    except ET.ParseError as exc:
        check("favourites.xml ist gültiges XML", False, exc)

    section("Lizenzen: Widevine nicht im Image")
    pk = open(os.path.join(ROOT, "stage-echoos/00-echoos/00-packages")).read().split()
    check("libwidevinecdm0 ist nicht in der Paketliste des Images", "libwidevinecdm0" not in pk)
    chroot = open(os.path.join(ROOT, "stage-echoos/00-echoos/02-run-chroot.sh")).read()
    check("Erststart-Dienst echoos-widevine wird aktiviert", "echoos-widevine.service" in chroot
          and os.path.exists(os.path.join(FS, "etc/systemd/system/echoos-widevine.service")))
    check("Lizenzhinweise liegen im Image", os.path.exists(os.path.join(FS, "usr/share/doc/echoos/LIZENZEN.md")))

    # ------------------------------------------------------------ Kodi-Addon
    section("Kodi-Addon 'Streaming'")
    addon = os.path.join(FS, "home/echoos/.kodi/addons/plugin.program.echoos.streaming/default.py")
    stub_log = os.path.join(work, "xbmc.jsonl")
    aenv = {**env, "PYTHONPATH": os.path.join(HERE, "stub_xbmc"), "XBMC_STUB_LOG": stub_log}
    src = open(addon).read().replace('"/usr/share/echoos/services.json"', repr(SERVICES))
    tmp_addon = os.path.join(work, "default.py")
    open(tmp_addon, "w").write(src)
    def kodi_run(query):
        # Kodi ruft Plugins mit argv = [Plugin-URL, Handle, Query] auf
        code = ("import sys, runpy; sys.argv = ['plugin://plugin.program.echoos.streaming/', '1', %r];"
                " runpy.run_path(%r, run_name='__main__')" % (query, tmp_addon))
        subprocess.run([PY, "-c", code], env=aenv, check=False)

    kodi_run("")
    calls = [json.loads(ln) for ln in open(stub_log)] if os.path.exists(stub_log) else []
    items = [c for c in calls if c["call"] == "addDirectoryItem"]
    check("Addon listet alle Streaming-Apps", len(items) == len(services), len(items))
    check("Jede Kachel hat ein Bild", all(i["art"].get("thumb", "").endswith(".png") for i in items))
    open(syslog, "a").close()
    before = open(syslog).read()
    kodi_run("?launch=netflix")
    time.sleep(0.5)
    new = open(syslog).read()[len(before):]
    check("Klick auf Netflix startet echoos-browser@netflix", "start --no-block echoos-browser@netflix.service" in new, new)
    kodi_run("?launch=evil;rm")
    aenv["ECHOOS_TEST_NO_WIDEVINE"] = "1"
    before = open(syslog).read()
    open(stub_log, "w").close()
    kodi_run("?launch=disneyplus")
    started = "echoos-browser@disneyplus" in open(syslog).read()[len(before):]
    hint = any(json.loads(l).get("call") == "notification" and "DRM" in json.loads(l).get("message", "")
               for l in open(stub_log) if l.strip())
    check("Ohne Widevine: DRM-Dienst startet nicht, Hinweis erscheint", not started and hint)
    del aenv["ECHOOS_TEST_NO_WIDEVINE"]
    check("Unbekannte Dienste werden abgelehnt", "evil" not in open(syslog).read())

    # ------------------------------------------------------------ Konfiguration
    section("Erststart-Konfiguration (echoos.conf)")
    boot = os.path.join(work, "echoos.conf")
    conf_text = open(os.path.join(ROOT, "stage-echoos/00-echoos/files/boot/echoos.conf")).read()
    conf_text = (conf_text.replace("ssid =", "ssid = MeinWLAN", 1)
                 .replace("[wlan]\n# Leer lassen, wenn der Pi per Netzwerkkabel angeschlossen ist.\ncountry = DE\nssid = MeinWLAN\npassword =",
                          "[wlan]\n# Leer lassen, wenn der Pi per Netzwerkkabel angeschlossen ist.\ncountry = DE\nssid = MeinWLAN\npassword = geheim123")
                 .replace("claude_api_key =", "claude_api_key = sk-ant-test"))
    open(boot, "w").write(conf_text)
    spec = importlib.util.spec_from_file_location("cfg", os.path.join(FS, "usr/local/lib/echoos/echoos_config.py"))
    os.environ.update({"ECHOOS_TEST_LOG": syslog, "PATH": env["PATH"]})
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    cfg.AGENT_CONF = os.path.join(work, "etc/agent.conf")
    import configparser
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(boot)
    cfg.apply_wifi(cp["wlan"]["country"], cp["wlan"]["ssid"], cp["wlan"]["password"])
    cfg.write_agent_conf(cp["agent"])
    scrubbed = cfg.scrub_secrets(boot)
    after = open(boot).read()
    agent_conf = open(cfg.AGENT_CONF).read()
    check("WLAN wird über NetworkManager angelegt", "nmcli connection add type wifi" in open(syslog).read())
    check("API-Schlüssel landet geschützt in agent.conf", "sk-ant-test" in agent_conf
          and oct(os.stat(cfg.AGENT_CONF).st_mode)[-3:] == "600")
    token_line = [ln for ln in agent_conf.splitlines() if ln.startswith("token")]
    check("Zugangscode wird erzeugt (8 Zeichen)", token_line and len(token_line[0].split("=")[1].strip()) == 8)
    check("Passwort + API-Schlüssel aus Boot-Datei gelöscht", scrubbed and "geheim123" not in after and "sk-ant-test" not in after)
    check("Kommentare und übrige Werte bleiben erhalten", "ssid = MeinWLAN" in after and "Grundeinstellungen" in after)

    # ------------------------------------------------------------ Agent
    section("KI-Agent: Kodi-Steuerung, Laufwerke, Chat, Updates, Sicherheit")
    kodi_log = os.path.join(OUT, "kodi_jsonrpc_calls.jsonl")
    open(kodi_log, "w").close()
    start([PY, os.path.join(HERE, "mock_kodi.py"), "19090", kodi_log], log=os.path.join(OUT, "mock_kodi.log"))
    start([PY, os.path.join(HERE, "fake_claude.py"), "18099"])
    kodi_home = os.path.join(work, "kodi")
    db_dir = os.path.join(kodi_home, "userdata/Database")
    os.makedirs(db_dir)
    db = os.path.join(db_dir, "MyVideos131.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE path (idPath integer primary key, strPath text, strContent text, strScraper text,"
                " strHash text, scanRecursive integer, useFolderNames bool, strSettings text, noUpdate bool,"
                " exclude bool, allAudio bool, dateAdded text, idParentPath integer)")
    con.commit()
    con.close()
    media = os.path.join(work, "media")
    drive = os.path.join(media, "FILME-HDD")
    for d in ("Filme/Tron (1982)", "Serien/Dark/Season 1", "Musik/Neon Drive", "Fotos"):
        os.makedirs(os.path.join(drive, d))
    mounts = os.path.join(work, "mounts")
    open(mounts, "w").write("/dev/mmcblk0p2 / ext4 rw 0 0\n")

    def agent_env(port, key):
        conf = os.path.join(work, f"agent{port}.conf")
        open(conf, "w").write(f"[agent]\ntoken = testcode\nport = {port}\nclaude_api_key = {key}\n"
                              "model = claude-haiku-5-5\nauto_reboot = yes\n")
        return {**env, "ECHOOS_AGENT_CONF": conf, "ECHOOS_STATE": os.path.join(work, f"state{port}"),
                "ECHOOS_KODI_PORT": "19090", "ECHOOS_KODI_HOME": kodi_home,
                "ECHOOS_MEDIA_ROOT": media, "ECHOOS_MOUNTS_FILE": mounts,
                "ECHOOS_CLAUDE_URL": "http://127.0.0.1:18099/v1/messages"}

    start([PY, AGENT], env=agent_env(18090, ""), log=os.path.join(OUT, "agent_ohne_ki.log"))
    start([PY, AGENT], env=agent_env(18091, "test-key"), log=os.path.join(OUT, "agent_mit_ki.log"))
    ok = wait_port(19090) and wait_port(18090) and wait_port(18091) and wait_port(18099)
    check("Agent, Mock-Kodi und Mock-Claude starten", ok)
    time.sleep(2)

    st, _ = http(18090, "/api/status")
    check("Web-API ohne Code gesperrt (401)", st == 401, st)
    st, body = http(18090, "/api/status", token="testcode")
    check("Status mit Code abrufbar", st == 200 and body["system"]["kodi"] == "21.2", body.get("system"))
    st, page = 0, ""
    with urllib.request.urlopen("http://127.0.0.1:18090/") as r:
        st, page = r.status, r.read().decode()
    check("Web-Oberfläche wird ausgeliefert", st == 200 and "ECHO-OS" in page)

    # Laufwerk anstecken
    open(mounts, "a").write(f"/dev/sda1 {drive} exfat rw 0 0\n")
    time.sleep(12)
    rows = sqlite3.connect(db).execute("SELECT strPath, strContent, strScraper FROM path").fetchall()
    content = {os.path.basename(r[0].rstrip('/')): r[1] for r in rows}
    check("Ordner 'Filme' als Filme erkannt (TMDb-Scraper)", content.get("Filme") == "movies", rows)
    check("Ordner 'Serien' als Serien erkannt", content.get("Serien") == "tvshows", rows)
    calls = kodi_calls(kodi_log)
    scans = [c for c in calls if c["method"].endswith("Library.Scan") and c["params"].get("directory")]
    check("Bibliotheks-Scan für Filme, Serien und Musik gestartet", len(scans) >= 3, scans)
    notes = [c["params"]["message"] for c in calls if c["method"] == "GUI.ShowNotification"]
    check("Hinweis auf dem Fernseher: Laufwerk erkannt", any("FILME-HDD" in n for n in notes), notes)
    check("Streaming-Addon wird in Kodi freigeschaltet",
          any(c["method"] == "Addons.SetAddonEnabled" for c in calls), "")
    check("Zugangscode wird auf dem Fernseher angezeigt", any("testcode" in n for n in notes), notes)

    # Einfache Befehle (ohne KI)
    st, r = http(18090, "/api/chat", {"message": "starte Disney+"}, token="testcode")
    check("Ohne KI: 'starte Disney+' öffnet die App", st == 200 and "Disney+" in r["reply"]
          and "echoos-browser@disneyplus" in open(syslog).read(), r)
    st, r = http(18090, "/api/chat", {"message": "Status"}, token="testcode")
    check("Ohne KI: 'Status' liefert Systemdaten", "temperatur_c" in r.get("reply", ""), r)

    # Mit KI (simulierte Claude-API, echter Tool-Use-Ablauf)
    st, r = http(18091, "/api/chat", {"message": "Spiel die nächste Folge von Dark"}, token="testcode")
    check("Mit KI: sucht in der Bibliothek und spielt die nächste ungesehene Folge",
          st == 200 and r["actions"] == ["search_library", "play"] and "S01E04" in r["reply"], r)
    st, np = http(18091, "/api/status", token="testcode")
    check("Kodi spielt jetzt Dark S01E04", (np.get("now_playing") or {}).get("spielt", {}).get("episode") == 4, np.get("now_playing"))
    st, r = http(18091, "/api/chat", {"message": "Gibt es Updates?"}, token="testcode")
    check("Mit KI: prüft Updates und erkennt das Sicherheitsupdate",
          "openssl" in r.get("reply", "") and r["actions"] == ["check_updates"], r)

    # Aktionen
    st, r = http(18091, "/api/action", {"action": "apply_updates"}, token="testcode")
    check("Updates werden nicht installiert, während etwas läuft", "fehler" in r, r)
    st, r = http(18091, "/api/action", {"action": "security"}, token="testcode")
    check("Sicherheitsbericht: Firewall aktiv, keine Warnungen", r.get("firewall") and r.get("warnungen") == [], r)
    st, r = http(18091, "/api/action", {"action": "launch", "service": "netflix"}, token="testcode")
    check("Web-Button startet Netflix", r.get("dienst") == "Netflix", r)

    # Schutz gegen Raten des Codes
    for _ in range(11):
        http(18090, "/api/status", token="falsch")
    st, _ = http(18090, "/api/status", token="testcode")
    check("Nach 10 Fehlversuchen wird die IP 10 Minuten gesperrt", st == 401, st)

    # Code auf dem Fernseher anzeigen (ohne Anmeldung, höchstens alle 30 s)
    before = len(kodi_calls(kodi_log))
    st1, _ = http(18091, "/api/show-code", {})
    st2, _ = http(18091, "/api/show-code", {})
    new = [c for c in kodi_calls(kodi_log)[before:] if c["method"] == "GUI.ShowNotification"]
    check("Knopf 'Code anzeigen' blendet den Code auf dem Fernseher ein",
          st1 == 200 and any("testcode" in c["params"]["message"] for c in new), (st1, new))
    check("Knopf ist gegen Dauerauslösen gesperrt (30 s)", st2 == 429, st2)

    for p in PROCS:
        p.terminate()
    shutil.rmtree(work, ignore_errors=True)

    passed = sum(1 for r in RESULTS if r.get("ok"))
    total = sum(1 for r in RESULTS if "ok" in r)
    json.dump({"passed": passed, "total": total, "results": RESULTS},
              open(os.path.join(OUT, "report.json"), "w"), ensure_ascii=False, indent=1)
    print(f"\n{passed}/{total} Tests bestanden")
    return 0 if passed == total else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        for p in PROCS:
            p.kill()
