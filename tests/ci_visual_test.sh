#!/usr/bin/env bash
# Visueller Test mit ECHTER Software auf einem Linux-Rechner (z. B. GitHub-Runner):
#   1. Echtes Plymouth spielt den Echo-OS-Bootscreen in einer virtuellen Anzeige ab (Video)
#   2. Echtes Kodi startet mit der Echo-OS-Konfiguration (Screenshots)
#   3. Der Echo-Agent steuert dieses echte Kodi (Laufwerkserkennung, Hinweise)
#   4. Echtes Laufwerk (Loop-Device, exFAT) wird per automount.sh eingehängt
# Ergebnisse: tests/out/ci/
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FS="$HERE/../stage-echoos/00-echoos/files/rootfs"
OUT="$HERE/out/ci"; rm -rf "$OUT"; mkdir -p "$OUT"
export DISPLAY=:99
RES=1920x1080
STATUS=0
note() { echo "== $*" | tee -a "$OUT/ablauf.log"; }
fail() { echo "FEHLER: $*" | tee -a "$OUT/ablauf.log"; STATUS=1; }
grab() { ffmpeg -loglevel error -y -f x11grab -draw_mouse 0 -video_size $RES -i :99 -frames:v 1 "$OUT/$1.png"; }

note "Pakete installieren"
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
    xvfb ffmpeg plymouth plymouth-x11 plymouth-label kodi python3-pil \
    fonts-dejavu-core exfatprogs jq sqlite3 >/dev/null || fail "Paketinstallation"

Xvfb :99 -screen 0 ${RES}x24 >/dev/null 2>&1 &
XVFB=$!
sleep 2

# ---------------------------------------------------------------- Plymouth
note "Bootscreen-Theme installieren"
THEME=/usr/share/plymouth/themes/echo
sudo mkdir -p $THEME
sudo cp "$FS/usr/share/plymouth/themes/echo/"* $THEME/
sudo python3 "$FS/usr/local/lib/echoos/gen_bootscreen.py" $THEME || fail "Grafiken erzeugen"
sudo cp $THEME/splash.jpg "$OUT/kodi_splash.jpg"
if command -v plymouth-set-default-theme >/dev/null; then
    sudo plymouth-set-default-theme echo
else
    sudo update-alternatives --install /usr/share/plymouth/themes/default.plymouth \
        default.plymouth $THEME/echo.plymouth 300
    sudo update-alternatives --set default.plymouth $THEME/echo.plymouth
fi

note "Echtes Plymouth starten und aufnehmen"
# Auf langsamen CI-Rechnern ist plymouthd nach festen Wartezeiten manchmal noch
# nicht bereit. Deshalb: warten bis er antwortet, und bis zu 3 Versuche.
plymouth_run() {
    sudo rm -f "$OUT/plymouth_debug.log"
    ffmpeg -loglevel error -y -f x11grab -draw_mouse 0 -framerate 25 -video_size $RES -i :99 -t 14 \
        -c:v libx264 -preset veryfast -crf 22 -pix_fmt yuv420p "$OUT/plymouth_echt.mp4" &
    local rec=$!
    # Dieselben Kernel-Parameter wie auf dem Pi (cmdline.txt von Echo-OS)
    sudo -E plymouthd --no-daemon --debug --debug-file="$OUT/plymouth_debug.log" \
        --kernel-command-line="quiet splash loglevel=3 plymouth.ignore-serial-consoles" &
    local ok=0
    for _ in $(seq 1 40); do sudo plymouth --ping 2>/dev/null && { ok=1; break; }; sleep 0.25; done
    if [ $ok -eq 1 ]; then
        sleep 1
        sudo plymouth show-splash
        sleep 3;  sudo plymouth message --text="Dateisystem wird geprüft …"
        sleep 1;  grab plymouth_screenshot
        sleep 3;  sudo plymouth message --text="Netzwerk wird gestartet …"
        sleep 4
        sudo plymouth --ping 2>/dev/null || ok=0      # noch am Leben?
        sudo plymouth quit --retain-splash 2>/dev/null || sudo plymouth quit 2>/dev/null
    fi
    wait $rec
    sudo pkill -x plymouthd 2>/dev/null
    sudo chmod a+r "$OUT/plymouth_debug.log" 2>/dev/null
    [ $ok -eq 1 ] && grep -q "executing script file" "$OUT/plymouth_debug.log" 2>/dev/null
}
PLY_OK=0
for attempt in 1 2 3; do
    if plymouth_run; then PLY_OK=1; break; fi
    note "Plymouth-Versuch $attempt nicht vollständig – neuer Versuch"
    sleep 2
done
[ $PLY_OK -eq 1 ] || fail "Plymouth hat das Echo-Skript nach 3 Versuchen nicht vollständig abgespielt (siehe plymouth_debug.log)"
grep -qi "parse error\|script error" "$OUT/plymouth_debug.log" 2>/dev/null && fail "Plymouth meldet Skriptfehler"

# ---------------------------------------------------------------- Kodi
note "Kodi mit Echo-OS-Konfiguration vorbereiten"
export HOME="$OUT/home"
mkdir -p "$HOME"
cp -a "$FS/home/echoos/.kodi" "$HOME/"
sudo mkdir -p /usr/share/echoos
sudo cp "$FS/usr/share/echoos/services.json" /usr/share/echoos/
sudo ECHOOS_TILE_DIR=/usr/share/echoos/tiles python3 "$FS/usr/local/lib/echoos/gen_tiles.py"
python3 "$FS/usr/local/lib/echoos/gen_favourites.py" > "$HOME/.kodi/userdata/favourites.xml"
cp /usr/share/echoos/tiles/_addon_icon.png "$HOME/.kodi/addons/plugin.program.echoos.streaming/icon.png"
mkdir -p "$HOME/.kodi/media" && cp "$OUT/kodi_splash.jpg" "$HOME/.kodi/media/splash.jpg"

note "Streaming-Addon vorab aktivieren (wie echoos-config.service vor Kodi)"
ECHOOS_KODI_DB_DIR="$HOME/.kodi/userdata/Database" python3 -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('cfg', '$FS/usr/local/lib/echoos/echoos_config.py')
cfg = importlib.util.module_from_spec(spec); spec.loader.exec_module(cfg); cfg.enable_kodi_addons()" || fail "Addon-Vorab-Aktivierung"

note "Echtes Kodi starten"
LIBGL_ALWAYS_SOFTWARE=1 kodi --standalone --windowing=x11 >"$OUT/kodi_stdout.log" 2>&1 &
KODI=$!
sleep 3; grab kodi_01_startbild
rpc() { python3 - "$1" <<'PY'
import json, socket, sys
s = socket.create_connection(("127.0.0.1", 9090), timeout=10)
s.sendall(sys.argv[1].encode())
buf, dec = "", json.JSONDecoder()
while True:
    buf += s.recv(65536).decode("utf-8", "replace")
    try:
        while buf:
            obj, i = dec.raw_decode(buf.lstrip()); buf = buf.lstrip()[i:]
            if obj.get("id") == 1:
                print(json.dumps(obj)); sys.exit(0)
    except ValueError:
        continue
PY
}
for i in $(seq 1 60); do rpc '{"jsonrpc":"2.0","id":1,"method":"JSONRPC.Ping"}' >/dev/null 2>&1 && break; sleep 1; done
rpc '{"jsonrpc":"2.0","id":1,"method":"JSONRPC.Ping"}' | grep -q pong || fail "Kodi JSON-RPC (Port 9090) nicht erreichbar"
sleep 8; grab kodi_02_hauptmenue

note "Echo-Agent mit echtem Kodi starten"
mkdir -p "$OUT/agent" "$OUT/media"
printf '[agent]\ntoken = citest\nport = 8090\n' > "$OUT/agent/agent.conf"
ECHOOS_AGENT_CONF="$OUT/agent/agent.conf" ECHOOS_STATE="$OUT/agent/state" \
ECHOOS_KODI_HOME="$HOME/.kodi" ECHOOS_MEDIA_ROOT=/media \
    sudo -E python3 "$FS/opt/echoos/agent/echoos_agent.py" >"$OUT/agent/agent.log" 2>&1 &
AGENT=$!
sleep 6; grab kodi_03_agent_zugangscode

note "Favoriten (Streaming-Apps) öffnen"
rpc '{"jsonrpc":"2.0","id":1,"method":"GUI.ActivateWindow","params":{"window":"favouritesbrowser"}}' >/dev/null
sleep 4; grab kodi_04_favoriten
rpc '{"jsonrpc":"2.0","id":1,"method":"Addons.GetAddonDetails","params":{"addonid":"plugin.program.echoos.streaming","properties":["enabled"]}}' \
    | tee "$OUT/addon_status.json" | grep -q '"enabled": true' || fail "Streaming-Addon nicht aktiviert"
rpc '{"jsonrpc":"2.0","id":1,"method":"GUI.ActivateWindow","params":{"window":"videos","parameters":["plugin://plugin.program.echoos.streaming/"]}}' >/dev/null
sleep 5; grab kodi_05_streaming_addon

note "Echtes Laufwerk anstecken (exFAT-Image mit Filme/Serien)"
sudo useradd -M echoos 2>/dev/null || true
truncate -s 256M "$OUT/disk.img"
mkfs.exfat -L FILME-HDD "$OUT/disk.img" >/dev/null
LOOP=$(sudo losetup -fP --show "$OUT/disk.img")
sudo mkdir -p /mnt/prep
if ! sudo mount "$LOOP" /mnt/prep 2>/dev/null; then
    note "Kernel ohne exFAT – Laufwerk wird stattdessen als ext4 formatiert"
    sudo mkfs.ext4 -q -L FILME-HDD "$LOOP"
    sudo mount "$LOOP" /mnt/prep
fi
sudo mkdir -p "/mnt/prep/Filme/Tron (1982)" "/mnt/prep/Serien/Dark/Season 1"
sudo umount /mnt/prep
sudo sh "$FS/usr/local/lib/echoos/automount.sh" "$LOOP"
sleep 3
findmnt /media/FILME-HDD | tee "$OUT/mount.txt" || fail "automount.sh hat das Laufwerk nicht eingehängt"
rpc '{"jsonrpc":"2.0","id":1,"method":"GUI.ActivateWindow","params":{"window":"home"}}' >/dev/null
for i in $(seq 1 40); do grep -q "Laufwerk FILME-HDD erkannt" "$OUT/agent/agent.log" && break; sleep 0.5; done
sleep 1; grab kodi_06_laufwerk_erkannt
DB=$(ls "$HOME"/.kodi/userdata/Database/MyVideos*.db 2>/dev/null | sort -V | tail -1)
sudo sqlite3 "$DB" "SELECT strPath, strContent FROM path WHERE strContent!='';" | tee "$OUT/bibliothek_zuordnung.txt"
grep -q "movies" "$OUT/bibliothek_zuordnung.txt" || fail "Filme-Ordner nicht der Bibliothek zugeordnet"

note "Aufräumen"
sudo kill $AGENT 2>/dev/null; kill $KODI 2>/dev/null; sleep 2
sudo systemd-umount /media/FILME-HDD 2>/dev/null || sudo umount /media/FILME-HDD 2>/dev/null
sudo losetup -d "$LOOP" 2>/dev/null; rm -f "$OUT/disk.img"
kill $XVFB 2>/dev/null
sudo chown -R "$(id -u):$(id -g)" "$OUT"
rm -rf "$OUT/home/.kodi/temp" "$OUT/home/.kodi/addons/packages"
[ $STATUS -eq 0 ] && note "Visueller Test erfolgreich" || note "Visueller Test mit Fehlern beendet"
exit $STATUS
