#!/bin/bash -e
# Läuft auf dem Build-Host. Kopiert unsere Dateien ins Root-Dateisystem.

cp -a files/rootfs/. "${ROOTFS_DIR}/"

install -m 644 files/boot/echoos.conf "${ROOTFS_DIR}/boot/firmware/echoos.conf"
install -m 644 files/rootfs/usr/share/doc/echoos/LIZENZEN.md "${ROOTFS_DIR}/boot/firmware/LIZENZEN.txt"

CFG="${ROOTFS_DIR}/boot/firmware/config.txt"
# Mehr CMA-Speicher für 4K-Hardwaredecoding
sed -i 's/^dtoverlay=vc4-kms-v3d.*/dtoverlay=vc4-kms-v3d,cma-512/' "$CFG"
cat files/boot/config-append.txt >> "$CFG"

# --- Bootscreen: Regenbogen-Splash und Kernel-Meldungen ausblenden ---
grep -q '^disable_splash=' "$CFG" || sed -i '1i disable_splash=1' "$CFG"
CMD="${ROOTFS_DIR}/boot/firmware/cmdline.txt"
sed -i 's/ console=tty1//; s/$/ console=tty3 quiet splash loglevel=3 plymouth.ignore-serial-consoles logo.nologo vt.global_cursor_default=0/' "$CMD"
