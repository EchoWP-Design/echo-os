#!/bin/bash
# Startet Mock-Kodi, Mock-Claude und den echten Agenten und nimmt die Web-Oberfläche auf.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
FS="$HERE/../stage-echoos/00-echoos/files/rootfs"
W="$(mktemp -d)"; OUT="$HERE/out/ui"; rm -rf "$OUT"; mkdir -p "$OUT"
mkdir -p "$W/media/FILME-HDD/Filme" "$W/media/FILME-HDD/Serien" "$W/kodi/userdata/Database"
echo "/dev/sda1 $W/media/FILME-HDD exfat rw 0 0" > "$W/mounts"
printf '[agent]\ntoken = testcode\nport = 18095\nclaude_api_key = test-key\n' > "$W/agent.conf"
python3 "$HERE/mock_kodi.py" 19095 "$W/kodi.jsonl" >/dev/null 2>&1 & P1=$!
python3 "$HERE/fake_claude.py" 18096 & P2=$!
PATH="$HERE/fakebin:$PATH" ECHOOS_TEST_LOG="$W/sys.log" ECHOOS_AGENT_CONF="$W/agent.conf" ECHOOS_STATE="$W/state" \
ECHOOS_SERVICES="$FS/usr/share/echoos/services.json" ECHOOS_KODI_PORT=19095 ECHOOS_KODI_HOME="$W/kodi" \
ECHOOS_MEDIA_ROOT="$W/media" ECHOOS_MOUNTS_FILE="$W/mounts" ECHOOS_CLAUDE_URL="http://127.0.0.1:18096/v1/messages" \
python3 "$FS/opt/echoos/agent/echoos_agent.py" >"$OUT/agent.log" 2>&1 & P3=$!
trap 'kill $P1 $P2 $P3 2>/dev/null' EXIT
sleep 4
node "$HERE/ui_capture.mjs" "http://127.0.0.1:18095/" "$OUT"
ffmpeg -loglevel error -y -framerate 12 -pattern_type glob -i "$OUT/frames/*.jpg" \
  -vf "scale=1280:-2,format=yuv420p" -c:v libx264 -preset veryfast -crf 26 "$OUT/web_ui_session.mp4"
rm -rf "$OUT/frames"
echo "Aufnahme: $OUT/web_ui_session.mp4"
