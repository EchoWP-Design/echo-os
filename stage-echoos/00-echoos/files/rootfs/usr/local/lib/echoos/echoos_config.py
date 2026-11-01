#!/usr/bin/env python3
"""Übernimmt bei jedem Start die Einstellungen aus /boot/firmware/echoos.conf.

Geheimnisse (Passwörter, API-Schlüssel) werden danach aus der Datei auf der
Boot-Partition gelöscht und nur noch geschützt im System gespeichert.
"""
import configparser
import os
import pwd
import re
import glob
import secrets
import sqlite3
import string
import subprocess

BOOT_CONF = os.environ.get("ECHOOS_BOOT_CONF", "/boot/firmware/echoos.conf")
AGENT_CONF = os.environ.get("ECHOOS_AGENT_CONF", "/etc/echoos/agent.conf")
STATE = os.environ.get("ECHOOS_STATE", "/var/lib/echoos")
USER = "echoos"
KODI_DB_DIR = os.environ.get("ECHOOS_KODI_DB_DIR", "/home/echoos/.kodi/userdata/Database")
OUR_ADDONS = ["plugin.program.echoos.streaming"]
# Hier liegen mitinstallierte Addons (Pakete wie kodi-inputstream-adaptive)
ADDON_DIRS = ["/usr/share/kodi/addons", "/usr/lib/*/kodi/addons", "/usr/lib/kodi/addons",
              "/home/echoos/.kodi/addons"]
SECRETS = {("system", "password"), ("wlan", "password"), ("agent", "claude_api_key")}


def sh(*cmd, quiet=False, **kw):
    try:
        return subprocess.run(cmd, check=False, capture_output=quiet, text=True, **kw)
    except FileNotFoundError:
        return None


def log(msg):
    print(f"echoos-config: {msg}", flush=True)


def scrub_secrets(path):
    """Leert die Werte geheimer Schlüssel, Kommentare bleiben erhalten."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    section, changed, out = None, False, []
    for line in lines:
        m = re.match(r"^\s*\[([^\]]+)\]", line)
        if m:
            section = m.group(1).strip().lower()
        kv = re.match(r"^(\s*)([A-Za-z_]+)(\s*=\s*)(.*?)\s*$", line)
        if kv and (section, kv.group(2).lower()) in SECRETS and kv.group(4):
            line = f"{kv.group(1)}{kv.group(2)}{kv.group(3)}\n"
            changed = True
        out.append(line)
    if changed:
        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(out)
        os.sync()
    return changed


def apply_hostname(name):
    name = re.sub(r"[^a-z0-9-]", "", name.lower())[:63]
    if not name:
        return
    current = open("/etc/hostname").read().strip() if os.path.exists("/etc/hostname") else ""
    if name == current:
        return
    with open("/etc/hostname", "w") as fh:
        fh.write(name + "\n")
    if os.path.exists("/etc/hosts"):
        hosts = open("/etc/hosts").read()
        hosts = re.sub(r"^127\.0\.1\.1\s+.*$", f"127.0.1.1\t{name}", hosts, flags=re.M)
        if "127.0.1.1" not in hosts:
            hosts += f"127.0.1.1\t{name}\n"
        open("/etc/hosts", "w").write(hosts)
    sh("hostname", name)
    log(f"Hostname: {name}")


def apply_timezone(tz):
    if tz and os.path.exists(f"/usr/share/zoneinfo/{tz}"):
        sh("timedatectl", "set-timezone", tz)


def apply_wifi(country, ssid, psk):
    if country:
        sh("raspi-config", "nonint", "do_wifi_country", country.upper())
    if not ssid:
        return
    # Das WLAN-Passwort wird nach dem ersten Start aus echoos.conf gelöscht. Ist es leer
    # und die Verbindung existiert schon, nichts anfassen – sonst würde sie ohne
    # Passwort neu angelegt und der Pi verliert das WLAN.
    exists = sh("nmcli", "-t", "-f", "NAME", "connection", "show", quiet=True)
    if not psk and exists and "echoos-wlan" in (exists.stdout or "").split():
        return
    sh("rfkill", "unblock", "wifi")
    sh("nmcli", "connection", "delete", "echoos-wlan", quiet=True)
    cmd = ["nmcli", "connection", "add", "type", "wifi", "ifname", "wlan0",
           "con-name", "echoos-wlan", "ssid", ssid, "connection.autoconnect", "yes"]
    if psk:
        cmd += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", psk]
    sh(*cmd, quiet=True)
    sh("nmcli", "connection", "up", "echoos-wlan", quiet=True)
    log(f"WLAN eingerichtet: {ssid}")


def apply_password(password):
    if password:
        sh("chpasswd", input=f"{USER}:{password}\n")
        log("Benutzerpasswort gesetzt")


def ensure_random_password():
    marker = os.path.join(STATE, "password.initialized")
    if os.path.exists(marker):
        return
    pw = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
    sh("chpasswd", input=f"{USER}:{pw}\n")
    open(marker, "w").close()
    log("Zufälliges Benutzerpasswort gesetzt (Build-Passwort entfernt)")


def apply_ssh(pubkey):
    pubkey = pubkey.strip()
    if not pubkey:
        return
    if not re.match(r"^(ssh-(ed25519|rsa)|ecdsa-sha2-\S+|sk-\S+) [A-Za-z0-9+/=]+", pubkey):
        log("SSH-Schlüssel hat ein unbekanntes Format – ignoriert")
        return
    pw = pwd.getpwnam(USER)
    ssh_dir = os.path.join(pw.pw_dir, ".ssh")
    os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
    keys_file = os.path.join(ssh_dir, "authorized_keys")
    existing = open(keys_file).read() if os.path.exists(keys_file) else ""
    if pubkey not in existing:
        with open(keys_file, "a") as fh:
            fh.write(pubkey + "\n")
    os.chmod(keys_file, 0o600)
    os.chown(ssh_dir, pw.pw_uid, pw.pw_gid)
    os.chown(keys_file, pw.pw_uid, pw.pw_gid)
    os.makedirs("/etc/ssh/sshd_config.d", exist_ok=True)
    with open("/etc/ssh/sshd_config.d/10-echoos.conf", "w") as fh:
        fh.write("PasswordAuthentication no\nKbdInteractiveAuthentication no\n"
                 "PermitRootLogin no\nAllowUsers echoos\n")
    sh("systemctl", "enable", "ssh.service")
    # Nicht warten: Dieser Dienst ist "Before=ssh.service" geordnet. Ein blockierendes
    # "start" würde auf sich selbst warten und den Start von Kodi verhindern.
    sh("systemctl", "start", "--no-block", "ssh.service")
    log("SSH mit Schlüssel aktiviert")


ADDON_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS version (idVersion integer, iCompressCount integer);
CREATE TABLE IF NOT EXISTS addons (id INTEGER PRIMARY KEY,metadata BLOB,addonID TEXT NOT NULL,version TEXT NOT NULL,name TEXT NOT NULL,summary TEXT NOT NULL,news TEXT NOT NULL,description TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS repo (id integer primary key, addonID text,checksum text, lastcheck text, version text, nextcheck TEXT);
CREATE TABLE IF NOT EXISTS addonlinkrepo (idRepo integer, idAddon integer);
CREATE TABLE IF NOT EXISTS update_rules (id integer primary key, addonID TEXT, updateRule INTEGER);
CREATE TABLE IF NOT EXISTS package (id integer primary key, addonID text, filename text, hash text);
CREATE TABLE IF NOT EXISTS installed (id INTEGER PRIMARY KEY, addonID TEXT UNIQUE, enabled BOOLEAN, installDate TEXT, lastUpdated TEXT, lastUsed TEXT, origin TEXT NOT NULL DEFAULT '', disabledReason INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idxAddons ON addons(addonID);
CREATE UNIQUE INDEX IF NOT EXISTS ix_addonlinkrepo_1 ON addonlinkrepo ( idAddon, idRepo );
CREATE UNIQUE INDEX IF NOT EXISTS ix_addonlinkrepo_2 ON addonlinkrepo ( idRepo, idAddon );
CREATE UNIQUE INDEX IF NOT EXISTS idxUpdate_rules ON update_rules(addonID, updateRule);
CREATE UNIQUE INDEX IF NOT EXISTS idxPackage ON package(filename);
"""


def enable_kodi_addons():
    """Markiert alle mitinstallierten Addons in Kodis Datenbank als aktiviert, bevor Kodi
    startet. Ohne das fragt Kodi beim ersten Start für jedes neu gefundene Addon
    "Add-on aktivieren?" und blockiert die Oberfläche."""
    found = set(OUR_ADDONS)
    for pattern in ADDON_DIRS + [os.path.join(os.path.dirname(KODI_DB_DIR.rstrip("/")), "..", "addons")]:
        for base in glob.glob(pattern):
            for xml in glob.glob(os.path.join(base, "*", "addon.xml")):
                found.add(os.path.basename(os.path.dirname(xml)))
    os.makedirs(KODI_DB_DIR, exist_ok=True)
    dbs = sorted(glob.glob(os.path.join(KODI_DB_DIR, "Addons*.db")),
                 key=lambda p: int(re.sub(r"\D", "", os.path.basename(p)) or 0))
    db = dbs[-1] if dbs else os.path.join(KODI_DB_DIR, "Addons33.db")
    fresh = not os.path.exists(db)
    try:
        con = sqlite3.connect(db, timeout=10)
        with con:
            if fresh:
                con.executescript(ADDON_DB_SCHEMA)
                con.execute("INSERT INTO version (idVersion, iCompressCount) VALUES (33, 0)")
            for addon in sorted(found):
                if addon == "packages":
                    continue
                con.execute("INSERT INTO installed (addonID, enabled, installDate, origin, disabledReason) "
                            "VALUES (?, 1, datetime('now'), '', 0) "
                            + ("ON CONFLICT(addonID) DO UPDATE SET enabled=1, disabledReason=0"
                               if addon in OUR_ADDONS else "ON CONFLICT(addonID) DO NOTHING"), (addon,))
        con.close()
        try:
            pw = pwd.getpwnam(USER)
            for path in (KODI_DB_DIR, db):
                os.chown(path, pw.pw_uid, pw.pw_gid)
        except KeyError:
            pass
    except sqlite3.Error as exc:
        log(f"Kodi-Addon-Datenbank: {exc}")


def write_agent_conf(agent_section):
    os.makedirs(os.path.dirname(AGENT_CONF), mode=0o700, exist_ok=True)
    conf = configparser.ConfigParser()
    conf.read(AGENT_CONF)
    if not conf.has_section("agent"):
        conf.add_section("agent")
    a = conf["agent"]
    if not a.get("token"):
        alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
        a["token"] = "".join(secrets.choice(alphabet) for _ in range(8))
    key = agent_section.get("claude_api_key", "").strip()
    if key:
        a["claude_api_key"] = key
    for opt in ("model", "auto_reboot", "workspace_id"):
        val = agent_section.get(opt, "").strip()
        if val:
            a[opt] = val
    fd = os.open(AGENT_CONF, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        conf.write(fh)


def main():
    os.makedirs(STATE, exist_ok=True)
    conf = configparser.ConfigParser(interpolation=None)
    if os.path.exists(BOOT_CONF):
        conf.read(BOOT_CONF, encoding="utf-8")

    def sec(name):
        return conf[name] if conf.has_section(name) else {}

    system, wlan, ssh, agent = sec("system"), sec("wlan"), sec("ssh"), sec("agent")

    ensure_random_password()
    apply_hostname(system.get("hostname", ""))
    apply_timezone(system.get("timezone", "").strip())
    apply_password(system.get("password", "").strip())
    apply_wifi(wlan.get("country", "").strip(), wlan.get("ssid", "").strip(),
               wlan.get("password", "").strip())
    apply_ssh(ssh.get("public_key", ""))
    write_agent_conf(agent)
    enable_kodi_addons()

    if os.path.exists(BOOT_CONF) and scrub_secrets(BOOT_CONF):
        log("Geheimnisse aus echoos.conf entfernt")


if __name__ == "__main__":
    main()
