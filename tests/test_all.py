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
    addon_dir = os.path.join(FS, "home/echoos/.kodi/addons/plugin.program.echoos.streaming")
    stub_log = os.path.join(work, "xbmc.jsonl")
    aenv = {**env, "PYTHONPATH": os.path.join(HERE, "stub_xbmc"), "XBMC_STUB_LOG": stub_log,
            "ECHOOS_SERVICES": SERVICES, "PYTHONDONTWRITEBYTECODE": "1"}
    tmp_addon = os.path.join(addon_dir, "default.py")
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

    # ------------------------------------------------------------ Addon auf Android
    section("Kodi-Addon auf Android (TV, Fire TV, Handy)")
    import sys as _sys
    _sys.dont_write_bytecode = True   # keine __pycache__-Ordner im Addon hinterlassen
    _sys.path.insert(0, os.path.join(addon_dir, "resources", "lib"))
    os.environ["ECHOOS_SERVICES"] = SERVICES
    import echostream as es
    svc = {s["id"]: s for s in services}
    check("Alle 18 Dienste haben Android-Paketnamen für TV und Handy",
          all(s.get("android", {}).get("tv") and s.get("android", {}).get("mobile") for s in services))
    tv_apps = {"com.google.android.youtube.tv": "YouTube", "com.netflix.ninja": "Netflix",
               "com.android.vending": "Google Play Store"}
    phone_apps = {"com.netflix.mediaclient": "Netflix", "com.android.vending": "Play Store",
                  "com.google.android.apps.youtube.music": "YouTube Music"}
    fire_apps = {"com.amazon.firetv.youtube": "YouTube", "com.amazon.venezia": "Appstore"}
    check("Android-TV-Gerät wird erkannt", es.is_tv(tv_apps) and not es.is_tv(phone_apps))
    check("Fire-TV-Gerät wird erkannt", es.is_tv(fire_apps))
    check("Einstellung 'Handy' übersteuert die Erkennung", not es.is_tv(tv_apps, "mobile"))
    check("Fernseher: Netflix startet die TV-App (com.netflix.ninja)",
          es.find_package(svc["netflix"], tv_apps, True) == "com.netflix.ninja")
    check("Handy: Netflix startet die Handy-App", es.find_package(svc["netflix"], phone_apps, False) == "com.netflix.mediaclient")
    check("App mit unbekanntem Paketnamen wird über ihren Namen gefunden",
          es.find_package(svc["zdf"], {"de.zdf.neu": "ZDF"}, True) == "de.zdf.neu")
    check("'YouTube Music' wird nicht für YouTube gehalten", es.find_package(svc["youtube"], phone_apps, False) is None)
    cmd = es.store_command(svc["disneyplus"], tv_apps, True)
    check("Fehlt die App, öffnet sich der Play Store", cmd ==
          "StartAndroidActivity(com.android.vending,android.intent.action.VIEW,,market://details?id=com.disney.disneyplus)", cmd)
    check("Play Store zeigt auf dem Fernseher die TV-Version", "id=de.swr.avp.ard.tv" in es.store_command(svc["ard"], tv_apps, True))
    check("Play Store zeigt auf dem Handy die Handy-Version", "id=de.swr.avp.ard)" in es.store_command(svc["ard"], phone_apps, False))
    check("Fire TV: Amazon Appstore statt Play Store",
          "amzn://apps/android?p=de.rtli.tvnow" in es.store_command(svc["rtlplus"], fire_apps, True))
    check("Ohne App-Store kein Startbefehl", es.store_command(svc["wow"], {"x.y": "Z"}, True) is None)

    android_env = {"XBMC_STUB_PLATFORM": "android", "XBMC_STUB_APPS": json.dumps(list(tv_apps.items()))}
    aenv.update(android_env)
    open(stub_log, "w").close()
    kodi_run("")
    calls = [json.loads(l) for l in open(stub_log) if l.strip()]
    labels = [c["label"] for c in calls if c["call"] == "addDirectoryItem"]
    check("Liste auf Android: installierte Apps normal, fehlende mit Hinweis 'installieren'",
          "Netflix" in labels and "YouTube" in labels and "Disney+ · installieren" in labels and len(labels) == 18, labels[:5])
    open(stub_log, "w").close()
    kodi_run("?launch=netflix")
    builtins = [c["command"] for c in (json.loads(l) for l in open(stub_log) if l.strip()) if c["call"] == "builtin"]
    check("Klick auf Netflix startet auf Android die Netflix-App", "StartAndroidActivity(com.netflix.ninja)" in builtins, builtins)
    before = open(syslog).read()
    open(stub_log, "w").close()
    kodi_run("?launch=disneyplus")
    builtins = [c["command"] for c in (json.loads(l) for l in open(stub_log) if l.strip()) if c["call"] == "builtin"]
    check("Klick auf fehlende App öffnet den Play Store", any("market://details?id=com.disney.disneyplus" in b for b in builtins), builtins)
    check("Auf Android wird nie der Pi-Browser gestartet", "echoos-browser" not in open(syslog).read()[len(before):])
    aenv["XBMC_STUB_SETTINGS"] = json.dumps({"onlyinstalled": True})
    open(stub_log, "w").close()
    kodi_run("")
    labels = [json.loads(l)["label"] for l in open(stub_log) if l.strip() and json.loads(l)["call"] == "addDirectoryItem"]
    check("Einstellung 'Nur installierte Apps' blendet fehlende aus", sorted(labels) == ["Netflix", "YouTube"], labels)
    for k in list(android_env) + ["XBMC_STUB_SETTINGS"]:
        aenv.pop(k, None)

    section("Neon-Startbild für Kodi (Addon-Dienst)")
    sp_addon = os.path.join(work, "addon_copy")
    shutil.copytree(addon_dir, sp_addon)
    os.makedirs(os.path.join(sp_addon, "resources", "media"))
    open(os.path.join(sp_addon, "resources", "media", "splash.jpg"), "wb").write(b"ECHO-NEON-1")
    home = os.path.join(work, "kodihome")
    senv = {**aenv, "XBMC_STUB_ADDON_PATH": sp_addon, "XBMC_STUB_HOME": home,
            "XBMC_STUB_PROFILE": os.path.join(work, "profile")}
    target = os.path.join(home, "media", "splash.jpg")
    def run_service(settings=None):
        e = dict(senv)
        if settings is not None:
            e["XBMC_STUB_SETTINGS"] = json.dumps(settings)
        subprocess.run([PY, os.path.join(sp_addon, "service.py")], env=e, check=False)
    run_service()
    check("Startbild wird angelegt, wenn keins da ist", open(target, "rb").read() == b"ECHO-NEON-1")
    open(os.path.join(sp_addon, "resources", "media", "splash.jpg"), "wb").write(b"ECHO-NEON-2")
    run_service()
    check("Eigenes (vom Addon gesetztes) Startbild wird bei Updates erneuert", open(target, "rb").read() == b"ECHO-NEON-2")
    run_service({"splash": False})
    check("Abschalten entfernt das Addon-Startbild", not os.path.exists(target))
    open(target, "wb").write(b"JANS-EIGENES-BILD")
    run_service()
    run_service({"splash": False})
    check("Ein eigenes Startbild des Nutzers wird nie angefasst", open(target, "rb").read() == b"JANS-EIGENES-BILD")

    section("Kodi-Addon als ZIP")
    zdir = os.path.join(work, "zip")
    r = subprocess.run([PY, os.path.join(ROOT, "tools/build_kodi_addon.py"), zdir], capture_output=True, text=True)
    zpath = r.stdout.strip()
    import zipfile as _zf
    names = _zf.ZipFile(zpath).namelist() if zpath and os.path.exists(zpath) else []
    pre = "plugin.program.echoos.streaming/"
    need = [pre + n for n in ("addon.xml", "default.py", "service.py", "icon.png", "fanart.jpg", "LIZENZEN.md",
                              "resources/services.json", "resources/settings.xml", "resources/media/splash.jpg",
                              "resources/lib/echostream.py",
                              "resources/language/resource.language.de_de/strings.po")]
    check("ZIP wird gebaut und enthält Addon, Einstellungen, Startbild, Lizenzen", all(n in names for n in need),
          [n for n in need if n not in names] or r.stderr[-300:])
    check("ZIP enthält alle 18 Kacheln", sum(1 for n in names if n.startswith(pre + "resources/tiles/")) == 18)
    check("Dateiname trägt die Addon-Version", zpath.endswith("plugin.program.echoos.streaming-1.1.0.zip"), zpath)
    try:
        ET.fromstring(_zf.ZipFile(zpath).read(pre + "addon.xml"))
        ET.fromstring(_zf.ZipFile(zpath).read(pre + "resources/settings.xml"))
        check("addon.xml und settings.xml sind gültiges XML", True)
    except Exception as exc:  # noqa: BLE001
        check("addon.xml und settings.xml sind gültiges XML", False, exc)

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
