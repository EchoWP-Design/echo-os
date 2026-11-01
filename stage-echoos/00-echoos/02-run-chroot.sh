#!/bin/bash -e
# Läuft im Image (chroot). Benutzer, Rechte und Dienste einrichten.

U=echoos
H=/home/$U

usermod -aG video,audio,input,render,plugdev,netdev "$U"

# sudo nur mit Passwort (nie NOPASSWD). Ohne eigenes Passwort in echoos.conf
# setzt Echo-OS ein Zufallspasswort – dann ist sudo praktisch gesperrt.
rm -f /etc/sudoers.d/010_pi-nopasswd
grep -l "NOPASSWD" /etc/sudoers.d/* 2>/dev/null | xargs -r rm -f
usermod -aG sudo,systemd-journal "$U"

# Einrichtung läuft über echoos.conf, nicht über cloud-init
mkdir -p /etc/cloud && touch /etc/cloud/cloud-init.disabled

chmod 755 /usr/local/bin/echoos-* /usr/local/lib/echoos/*.sh /usr/local/lib/echoos/*.py
chmod 755 /opt/echoos/agent/echoos_agent.py
mkdir -p /etc/echoos /var/lib/echoos /media
chmod 700 /etc/echoos /var/lib/echoos

# Kacheln für die Streaming-Apps und Kodi-Favoriten erzeugen
python3 /usr/local/lib/echoos/gen_tiles.py
python3 /usr/local/lib/echoos/gen_favourites.py > "$H/.kodi/userdata/favourites.xml"
cp /usr/share/echoos/tiles/_addon_icon.png \
   "$H/.kodi/addons/plugin.program.echoos.streaming/icon.png"

# Echo-OS Bootscreen (80er-Neon) erzeugen und aktivieren
python3 /usr/local/lib/echoos/gen_bootscreen.py /usr/share/plymouth/themes/echo
mkdir -p "$H/.kodi/media"
cp /usr/share/plymouth/themes/echo/splash.jpg "$H/.kodi/media/splash.jpg"
plymouth-set-default-theme echo
# Das initramfs (mit Bootscreen) erzeugt pi-gen im Export-Schritt neu
# (export-image/05-finalise: update-initramfs -k all -c).

# Systemname
sed -i 's/^PRETTY_NAME=.*/PRETTY_NAME="Echo-OS (Raspberry Pi OS Basis)"/' /etc/os-release

chown -R "$U:$U" "$H"

systemctl enable \
    seatd.service \
    kodi.service \
    echoos-config.service \
    echoos-agent.service \
    echoos-widevine.service \
    nftables.service \
    fail2ban.service \
    unattended-upgrades.service

# SSH erst aktivieren, wenn ein Schlüssel hinterlegt ist
systemctl disable ssh.service 2>/dev/null || true
# Festplatten-Gesundheit prüft der Agent selbst (smartctl); der Dauerdienst meldet
# ohne angeschlossene Platte nur einen Fehler beim Start.
systemctl disable smartmontools.service 2>/dev/null || true
# Kodi belegt tty1
systemctl disable getty@tty1.service 2>/dev/null || true
systemctl set-default multi-user.target
