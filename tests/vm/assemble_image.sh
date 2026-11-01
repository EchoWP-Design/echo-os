#!/usr/bin/env bash
# Setzt aus einem fertig gebauten pi-gen-Rootfs ein bootfähiges SD-Karten-Image zusammen,
# ganz ohne Mounten (für Testumgebungen ohne vfat/loop-Rechte).
# Auf GitHub erledigt das pi-gen selbst (export-image) – dieses Skript dient nur dem VM-Test.
# Aufruf: assemble_image.sh <rootfs-ordner> <ausgabe.img>
set -euo pipefail
ROOTFS="$1"; OUT="$2"
DISKID="ec0e0500"
BOOT_MB=512
WORK="$(dirname "$OUT")/assemble.$$"
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT

echo "== Test-Proxy-Konfiguration aus dem Build entfernen"
rm -f "$ROOTFS/etc/apt/apt.conf.d/99echoos-build-proxy" "$ROOTFS/etc/ssl/echoos-build-ca.crt"

echo "== PARTUUIDs eintragen (wie pi-gen export-image)"
sed -i "s/BOOTDEV/PARTUUID=${DISKID}-01/; s/ROOTDEV/PARTUUID=${DISKID}-02/" "$ROOTFS/etc/fstab"
sed -i "s/ROOTDEV/PARTUUID=${DISKID}-02/" "$ROOTFS/boot/firmware/cmdline.txt"
cat "$ROOTFS/etc/fstab"; cat "$ROOTFS/boot/firmware/cmdline.txt"

ROOT_MB=$(( $(du -sm "$ROOTFS" | cut -f1) * 13 / 10 + 400 ))
echo "== Boot-Partition (FAT32, ${BOOT_MB} MB) erstellen"
truncate -s ${BOOT_MB}M "$WORK/boot.img"
mkfs.vfat -F 32 -n bootfs "$WORK/boot.img" >/dev/null
mcopy -s -i "$WORK/boot.img" "$ROOTFS"/boot/firmware/* ::/

echo "== Root-Partition (ext4, ${ROOT_MB} MB) erstellen"
truncate -s ${ROOT_MB}M "$WORK/root.img"
mkfs.ext4 -q -L rootfs -d "$ROOTFS" "$WORK/root.img"

echo "== Image zusammensetzen"
START=8192
BOOT_SECT=$(( BOOT_MB * 2048 ))
ROOT_START=$(( START + BOOT_SECT ))
TOTAL_MB=$(( 4 + BOOT_MB + ROOT_MB + 4 ))
rm -f "$OUT"; truncate -s ${TOTAL_MB}M "$OUT"
sfdisk -q "$OUT" <<EOF
label: dos
label-id: 0x${DISKID}
start=${START}, size=${BOOT_SECT}, type=c
start=${ROOT_START}, type=83
EOF
dd if="$WORK/boot.img" of="$OUT" bs=1M seek=4 conv=notrunc status=none
dd if="$WORK/root.img" of="$OUT" bs=512 seek=${ROOT_START} conv=notrunc status=none
sfdisk -l "$OUT"
echo "Image: $OUT ($(du -h "$OUT" | cut -f1))"
