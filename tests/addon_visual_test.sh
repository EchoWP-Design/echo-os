#!/usr/bin/env bash
# Visueller Test des Kodi-Addons „Echo Streaming“ mit echtem Kodi (Linux, Xvfb):
#   1. ZIP bauen und so installieren, wie Kodi es selbst tut
#   2. Kachelansicht und Einstellungen aufnehmen
#   3. Kodi neu starten und das Neon-Startbild aufnehmen
# Ergebnisse: tests/out/addon/
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$HERE/.."
FS="$ROOT/stage-echoos/00-echoos/files/rootfs"
OUT="$HERE/out/addon"; rm -rf "$OUT"; mkdir -p "$OUT"
export DISPLAY=:98
RES=1920x1080
STATUS=0
note() { echo "== $*" | tee -a "$OUT/ablauf.log"; }
fail() { echo "FEHLER: $*" | tee -a "$OUT/ablauf.log"; STATUS=1; }
grab() { ffmpeg -loglevel error -y -f x11grab -draw_mouse 0 -video_size $RES -i :98 -frames:v 1 "$OUT/$1.png"; }
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
wait_kodi() { for _ in $(seq 1 90); do rpc '{"jsonrpc":"2.0","id":1,"method":"JSONRPC.Ping"}' 2>/dev/null | grep -q pong && return 0; sleep 1; done; return 1; }

if ! command -v kodi >/dev/null; then
    sudo apt-get update -q && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
        xvfb ffmpeg kodi kodi-eventclients-kodi-send python3-pil fonts-dejavu-core >/dev/null
fi

note "Addon-ZIP bauen"
ZIP=$(python3 "$ROOT/tools/build_kodi_addon.py" "$OUT/dist") || fail "ZIP-Bau"
cp "$ZIP" "$OUT/"

note "Wie Kodi installieren: entpacken nach ~/.kodi/addons und aktivieren"
export HOME="$OUT/home"; mkdir -p "$HOME/.kodi/addons" "$HOME/.kodi/userdata"
python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$ZIP" "$HOME/.kodi/addons"
# JSON-RPC und Eventserver (für kodi-send) einschalten, sonst Kodi-Standard
cat > "$HOME/.kodi/userdata/guisettings.xml" <<'EOF'
<settings version="2">
    <setting id="services.esenabled">true</setting>
    <setting id="services.esallinterfaces">false</setting>
</settings>
EOF
ECHOOS_KODI_DB_DIR="$HOME/.kodi/userdata/Database" python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('cfg', '$FS/usr/local/lib/echoos/echoos_config.py')
cfg = importlib.util.module_from_spec(spec); spec.loader.exec_module(cfg)
cfg.ADDON_DIRS = ['$HOME/.kodi/addons', '/usr/share/kodi/addons']
cfg.enable_kodi_addons()" || fail "Addons aktivieren"

Xvfb :98 -screen 0 ${RES}x24 >/dev/null 2>&1 & XVFB=$!
sleep 2

note "Kodi starten (erster Start: Addon-Dienst legt das Startbild ab)"
LIBGL_ALWAYS_SOFTWARE=1 kodi --standalone --windowing=x11 >"$OUT/kodi1.log" 2>&1 & KODI=$!
wait_kodi || fail "Kodi antwortet nicht"
sleep 6
[ -f "$HOME/.kodi/media/splash.jpg" ] && note "Startbild abgelegt: ~/.kodi/media/splash.jpg" || fail "Startbild wurde nicht abgelegt"
rpc '{"jsonrpc":"2.0","id":1,"method":"Addons.GetAddonDetails","params":{"addonid":"plugin.program.echoos.streaming","properties":["name","version","enabled"]}}' \
    | tee "$OUT/addon_details.json" | grep -q '"enabled": true' || fail "Addon nicht aktiv"

note "Kachelansicht öffnen"
rpc '{"jsonrpc":"2.0","id":1,"method":"GUI.ActivateWindow","params":{"window":"programs","parameters":["plugin://plugin.program.echoos.streaming/"]}}' >/dev/null
for i in $(seq 1 30); do
    n=$(rpc '{"jsonrpc":"2.0","id":1,"method":"XBMC.GetInfoLabels","params":{"labels":["Container.NumItems"]}}' \
        | python3 -c 'import sys,json; print(json.load(sys.stdin)["result"]["Container.NumItems"] or 0)' 2>/dev/null)
    [ "${n:-0}" -ge 18 ] 2>/dev/null && break; sleep 1
done
[ "${n:-0}" -ge 18 ] 2>/dev/null && note "Kacheln geladen: $n" || fail "Kacheln nicht geladen (${n:-0})"
sleep 4; grab 01_kacheln

note "Addon-Informationen und Einstellungen öffnen"
rpc '{"jsonrpc":"2.0","id":1,"method":"GUI.ActivateWindow","params":{"window":"home"}}' >/dev/null
sleep 2
kodi-send --action="Addon.OpenSettings(plugin.program.echoos.streaming)" >/dev/null 2>&1 || fail "kodi-send"
sleep 4; grab 02_einstellungen
kodi-send --action="Action(Back)" >/dev/null 2>&1; sleep 1

note "Kodi beenden und neu starten: Neon-Startbild"
rpc '{"jsonrpc":"2.0","id":1,"method":"Application.Quit"}' >/dev/null 2>&1
for _ in $(seq 1 20); do kill -0 $KODI 2>/dev/null || break; sleep 1; done
kill $KODI 2>/dev/null; sleep 1
mkdir -p "$OUT/start"
ffmpeg -loglevel error -y -f x11grab -draw_mouse 0 -framerate 4 -video_size $RES -i :98 -t 12 "$OUT/start/f%03d.png" & REC=$!
LIBGL_ALWAYS_SOFTWARE=1 kodi --standalone --windowing=x11 >"$OUT/kodi2.log" 2>&1 & KODI=$!
wait $REC
python3 - "$OUT" <<'PY' || STATUS=1
import glob, shutil, sys
from PIL import Image, ImageStat
out = sys.argv[1]
best, score = None, -1
for f in sorted(glob.glob(f"{out}/start/f*.png")):
    im = Image.open(f).convert("RGB").resize((96, 54))
    r, g, b = ImageStat.Stat(im).mean
    s = r + b - 1.5 * g          # Neon: viel Magenta/Violett, wenig Grün
    if s > score:
        best, score = f, s
if best is None or score < 40:
    print("FEHLER: Neon-Startbild nicht gefunden (Wert %.0f)" % score)
    sys.exit(1)
shutil.copy(best, f"{out}/03_startbild.png")
print("== Startbild gefunden in", best.rsplit("/", 1)[-1])
PY
rm -rf "$OUT/start" "$OUT/dist"

rpc '{"jsonrpc":"2.0","id":1,"method":"Application.Quit"}' >/dev/null 2>&1; sleep 2
kill $KODI $XVFB 2>/dev/null
rm -rf "$OUT/home/.kodi/temp" "$OUT/home/.kodi/addons/packages"
[ $STATUS -eq 0 ] && note "Addon-Test erfolgreich" || note "Addon-Test mit Fehlern beendet"
exit $STATUS
