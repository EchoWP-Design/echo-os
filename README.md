# Echo-OS

Ein Media-Center-Betriebssystem für den **Raspberry Pi 4 und 5** – mit Neon-Bootscreen im 80er-Stil, Kodi als Oberfläche, Streaming-Apps als Kacheln und einem KI-Agenten, der das System steuert und überwacht. Das Image wird mit **balenaEtcher** auf eine SD-Karte oder SSD geflasht.

## Was drin ist

| Bereich | Umsetzung |
|---|---|
| Basis | Raspberry Pi OS Lite (Debian 13 „Trixie“, 64-Bit) – wie LibreELEC auf gepflegtem Kernel und Treibern aufgebaut, damit Sicherheitsupdates weiter kommen |
| Bootscreen | Eigenes Plymouth-Theme: Synthwave-Sonne, Drahtgitter-Berge, endlos fahrendes Neon-Gitter, Chrom-Logo „ECHO-OS“, Tron-Lichtspur. Nahtloser Übergang ins Kodi-Startbild |
| Oberfläche | Kodi 21 mit Hardware-Decoding (H.264/HEVC, 4K60 HDR auf Pi 4/5) – spielt praktisch alle Formate: MKV, MP4, AVI, TS, FLAC, MP3, AAC, DTS, Dolby (Durchreichen an AV-Receiver) |
| Laufwerke | USB-Festplatten, SSDs und Sticks (exFAT, NTFS, ext4, FAT, btrfs, xfs) werden automatisch unter `/media/<Name>` eingehängt |
| Bibliothek | Ordner **Filme**, **Serien**, **Musik** auf einem Laufwerk werden automatisch erkannt, mit Postern und Infos (TMDb) eingelesen |
| Streaming | 18 Apps als Kacheln: Netflix, Prime Video, Disney+, YouTube, Apple TV+, Paramount+, WOW, RTL+, Joyn, MagentaTV, DAZN, ARD, ZDF, ARTE, Crunchyroll, Twitch, Spotify, Plex |
| KI-Agent | „ECHO“: Chat im Browser (`http://echo-os:8090`), steuert Kodi und Apps per natürlicher Sprache, überwacht Updates und Sicherheit |
| Sicherheit | Firewall (nur Heimnetz), automatische Sicherheitsupdates, fail2ban, SSH nur mit Schlüssel, kein passwortloses sudo, Zufallspasswort |

## Image bauen

**Variante A – GitHub (empfohlen, kein eigener Linux-Rechner nötig)**
1. Diesen Ordner als (privates) Repository auf GitHub hochladen.
2. Unter *Actions → Build Echo-OS → Run workflow* starten (dauert ca. 45–90 Minuten).
3. Das fertige `EchoOS-*.img.xz` unter *Artifacts* herunterladen.
   Mit einem Tag `v1.0` wird zusätzlich ein Release erstellt. Jeden Montag baut GitHub automatisch ein frisches Image mit allen aktuellen Updates.

**Variante B – eigener Linux-Rechner mit Docker**
```bash
./build.sh
# Ergebnis: deploy/EchoOS-*.img.xz
```

## Flashen und einrichten

1. **balenaEtcher** öffnen → *Flash from file* → `EchoOS-….img.xz` → SD-Karte/SSD wählen → *Flash*.
2. Karte am PC wieder einstecken, Laufwerk **bootfs** öffnen, Datei **`echoos.conf`** bearbeiten:
   - WLAN-Name und -Passwort (bei Netzwerkkabel leer lassen)
   - optional Claude-API-Schlüssel für den KI-Chat
   - optional SSH-Schlüssel
3. Karte in den Pi, starten. Nach dem Bootscreen erscheint Kodi; unten rechts wird die Adresse des KI-Agenten und der **Zugangscode** angezeigt.

Passwörter und API-Schlüssel werden beim Start übernommen und aus `echoos.conf` automatisch gelöscht.

## Bedienung

- **Fernbedienung des Fernsehers** funktioniert über HDMI-CEC direkt in Kodi.
- **Streaming-Apps:** Hauptmenü → *Favoriten* oder *Add-ons → Streaming*.
  Zurück zu Kodi: **Home-Taste**, **F12** oder **Zurück/ESC 1,5 Sekunden halten** (Tastatur/Air-Mouse), oder im Agenten „Zu Kodi“.
- **Laufwerk-Ordner:** Lege auf deiner Festplatte Ordner `Filme`, `Serien` und `Musik` an. Serien am besten als `Serien/Dark/Season 1/Dark S01E01.mkv`.
- **KI-Agent:** Browser auf Handy/PC → `http://echo-os:8090` (oder die IP) → Code eingeben. Beispiele:
  - „Spiel die nächste Folge von Dark“
  - „Starte Disney+“
  - „Gibt es Updates?“ / „Ist das System sicher?“
  - „Leiser“, „Pause“, „Untertitel an“

## Updates und Überwachung

- Sicherheits- und Systemupdates installieren sich täglich automatisch (unattended-upgrades), Kodi-Addons ebenfalls.
- Der Agent prüft alle 6 Stunden auf Updates und stündlich die Sicherheit: offene Ports, Firewall, SSH-Fehlversuche, gesperrte IPs, Festplatten-Gesundheit (SMART), Temperatur, Unterspannung, Speicherplatz. Probleme erscheinen als Hinweis auf dem Fernseher.
- Braucht ein Update einen Neustart, startet Echo-OS nachts um 4 Uhr neu – nur wenn gerade nichts läuft (abschaltbar mit `auto_reboot = no`).

## Tests

```bash
python3 tests/test_all.py      # 31 Funktionstests (ohne Pi lauffähig)
tests/run_ui_demo.sh           # Web-Oberfläche in Chrome aufnehmen
bash tests/ci_visual_test.sh   # echtes Plymouth + Kodi + Laufwerk (Linux, sudo)
# VM-Test eines gebauten Images (Raspberry Pi 3B in QEMU, Bildschirmaufnahme):
python3 tests/vm/qemu_boot.py deploy/EchoOS.img tests/out/vm 480
```
Hinweis zu QEMU: QEMU bildet die Pi-Grafik (VideoCore/KMS) nicht nach. Kernel, initramfs und systemd lassen sich dort prüfen, Bootscreen und Kodi zeigen sich erst auf echter Hardware.
Auf GitHub laufen alle Tests automatisch (*Actions → Echo-OS Tests*), Videos und Screenshots liegen dann unter *Artifacts*.

## Wichtige Hinweise

- **DRM-Streaming:** Netflix, Disney+, Prime & Co. laufen im Chromium-Browser mit Widevine. Das DRM-Modul ist nicht im Image enthalten, sondern wird beim **ersten Start mit Internet** automatisch aus der offiziellen Raspberry-Pi-Quelle installiert (dauert wenige Minuten). Auf Linux liefern manche Dienste nur **720p/1080p statt 4K**, und Anbieter können den Zugang ändern. Mediatheken, YouTube, Plex und lokale Dateien laufen in voller Qualität.
- **Hardware-Test:** Das Image wurde nicht auf einem echten Pi gebootet. Getestet sind alle Komponenten einzeln (siehe Testbericht). Beim ersten echten Start bitte auf Bild, Ton (HDMI) und Fernbedienung achten.
- Pi 5: H.264 wird per CPU dekodiert (der Pi 5 hat dafür keinen Hardware-Decoder) – für 1080p reicht das problemlos.

## Lizenzen und Marken

Erste stabile Version: Neon-Bootscreen, Kodi 21, 18 Streaming-Apps, automatische Laufwerkserkennung, KI-Agent ECHO
Echo-OS besteht aus freier Software auf Basis von Raspberry Pi OS (Debian 13). Kodi, der Linux-Kernel und viele weitere Bestandteile stehen unter der GPL und werden unverändert aus den offiziellen Paketquellen übernommen. Jedes Release enthält:
- die **`.info`-Datei** mit allen enthaltenen Paketen und Versionen,
- **`LIZENZEN.md`** mit den Lizenzen der wichtigsten Bestandteile und den Bezugsquellen des Quellcodes (liegt auch im Image unter `/usr/share/doc/echoos/` und auf der Boot-Partition als `LIZENZEN.txt`).

Das proprietäre DRM-Modul **Widevine** verteilt Echo-OS nicht selbst. „Kodi“ ist eine Marke der XBMC Foundation; Echo-OS ist ein unabhängiges Projekt („Powered by Kodi“) und wird von der Foundation weder unterstützt noch empfohlen.

## Projektstruktur

```
config                       pi-gen-Konfiguration (Name, Sprache, Stages)
build.sh                     Image bauen (Docker)
stage-echoos/00-echoos/
  00-packages                installierte Pakete
  01-run.sh / 02-run-chroot.sh  Einrichtung im Image
  files/boot/echoos.conf     Einstellungsdatei auf der Boot-Partition
  files/rootfs/…             alle Systemdateien (Dienste, Agent, Kodi, Bootscreen)
tests/                       Funktions- und visuelle Tests
.github/workflows/           Image-Build und Tests auf GitHub
```
