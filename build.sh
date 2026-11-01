#!/usr/bin/env bash
# Baut das Echo-OS-OS-Image mit pi-gen (in Docker).
# Ergebnis: deploy/*.img.xz  -> mit balenaEtcher flashen.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PIGEN_REPO="${PIGEN_REPO:-https://github.com/RPi-Distro/pi-gen.git}"
PIGEN_REF="${PIGEN_REF:-arm64}"          # arm64-Branch = 64-Bit-Image
WORK="$HERE/work"
PIGEN="$WORK/pi-gen"

command -v docker >/dev/null || { echo "Docker wird benötigt." >&2; exit 1; }

mkdir -p "$WORK"
if [ ! -d "$PIGEN/.git" ]; then
    git clone --depth 1 --branch "$PIGEN_REF" "$PIGEN_REPO" "$PIGEN"
else
    git -C "$PIGEN" fetch --depth 1 origin "$PIGEN_REF"
    git -C "$PIGEN" reset --hard FETCH_HEAD
fi

# Eigene Stage und Konfiguration einspielen
rm -rf "$PIGEN/stage-echoos"
cp -a "$HERE/stage-echoos" "$PIGEN/"
cp "$HERE/config" "$PIGEN/config"

# Kein eigenes Image für die Lite-Basis exportieren, nur für unsere Stage
touch "$PIGEN/stage2/SKIP_IMAGES"
chmod +x "$PIGEN"/stage-echoos/prerun.sh "$PIGEN"/stage-echoos/*/*.sh

# Alten Build-Container entfernen, sonst bricht build-docker.sh ab
docker rm -v pigen_work >/dev/null 2>&1 || true

(cd "$PIGEN" && ./build-docker.sh)

mkdir -p "$HERE/deploy"
cp -v "$PIGEN"/deploy/*.img.xz "$HERE/deploy/"
# Paketliste mit Versionen (für Lizenz- und Quellcode-Nachweise)
cp -v "$PIGEN"/deploy/*.info "$HERE/deploy/" 2>/dev/null || true
cp -v "$PIGEN"/deploy/*.sbom.xz "$HERE/deploy/" 2>/dev/null || true
cp -v "$HERE/stage-echoos/00-echoos/files/rootfs/usr/share/doc/echoos/LIZENZEN.md" "$HERE/deploy/"
echo
echo "Fertig. Image liegt in: $HERE/deploy/"
