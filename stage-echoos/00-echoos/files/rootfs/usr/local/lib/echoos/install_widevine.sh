#!/bin/sh
# Installiert das DRM-Modul Widevine (für Netflix, Prime Video, Disney+ …) beim ersten
# Start direkt aus der offiziellen Raspberry-Pi-Paketquelle.
# Widevine ist keine freie Software; Echo-OS verteilt es deshalb nicht selbst im Image.
set -e
MARKER=/var/lib/echoos/widevine.done
[ -f "$MARKER" ] && exit 0
if dpkg-query -W -f='${Status}' libwidevinecdm0 2>/dev/null | grep -q "install ok installed"; then
    touch "$MARKER"; exit 0
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q libwidevinecdm0
touch "$MARKER"
logger -t echoos "Widevine (DRM) aus der Raspberry-Pi-Paketquelle installiert"
