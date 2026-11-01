#!/bin/sh
# Wird von udev beim Anstecken eines Datenträgers aufgerufen.
# Hängt die Partition unter /media/<Label> ein (Systemlaufwerk ausgenommen).
DEV="$1"
[ -b "$DEV" ] || exit 0

PATH=/usr/sbin:/usr/bin:/sbin:/bin

# Partitionen der Systemplatte (SD-Karte, Boot-SSD) nie einhängen
ROOTSRC="$(findmnt -no SOURCE /)"
ROOTDISK="$(lsblk -no PKNAME "$ROOTSRC" 2>/dev/null)"
DISK="$(lsblk -no PKNAME "$DEV" 2>/dev/null)"
[ -n "$ROOTDISK" ] && [ "$DISK" = "$ROOTDISK" ] && exit 0

# Schon eingehängt? Dann nichts tun.
findmnt -rn -S "$DEV" >/dev/null 2>&1 && exit 0

TYPE="$(blkid -o value -s TYPE "$DEV")"
LABEL="$(blkid -o value -s LABEL "$DEV")"
[ -n "$LABEL" ] || LABEL="Laufwerk-$(blkid -o value -s UUID "$DEV" | cut -c1-8)"
# Nur sichere Zeichen im Ordnernamen
NAME="$(printf '%s' "$LABEL" | tr -c 'A-Za-z0-9._ -' '_' | sed 's/^[ .]*//; s/ *$//')"
[ -n "$NAME" ] || NAME="Laufwerk"

TARGET="/media/$NAME"
n=2
while findmnt -rn "$TARGET" >/dev/null 2>&1; do
    TARGET="/media/$NAME-$n"; n=$((n + 1))
done

UIDN="$(id -u echoos)"; GIDN="$(id -g echoos)"
OPTS="noatime,nosuid,nodev"
case "$TYPE" in
    vfat)  OPTS="$OPTS,uid=$UIDN,gid=$GIDN,umask=002,utf8" ;;
    exfat) OPTS="$OPTS,uid=$UIDN,gid=$GIDN,umask=002" ;;
    ntfs)
        # Schneller Kernel-Treiber, sonst ntfs-3g
        if modprobe -q ntfs3; then
            TYPE=ntfs3; OPTS="$OPTS,uid=$UIDN,gid=$GIDN,umask=002,prealloc"
        else
            TYPE=ntfs-3g; OPTS="$OPTS,uid=$UIDN,gid=$GIDN,umask=002,big_writes"
        fi ;;
esac

logger -t echoos-automount "Hänge $DEV ($TYPE) unter $TARGET ein"
if ! systemd-mount --no-block --collect -t "$TYPE" -o "$OPTS" "$DEV" "$TARGET" 2>/dev/null; then
    # Fallback ohne systemd (z. B. in Testumgebungen)
    mkdir -p "$TARGET" && mount -t "$TYPE" -o "$OPTS" "$DEV" "$TARGET"
fi
