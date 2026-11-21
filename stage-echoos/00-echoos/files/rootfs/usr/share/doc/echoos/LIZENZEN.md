# Echo-OS – Lizenzen und Quellcode

Echo-OS ist eine Zusammenstellung freier Software auf Basis von **Raspberry Pi OS**
(Debian 13 „Trixie“, arm64). Die enthaltenen Programme stehen unter ihren eigenen
Lizenzen; Echo-OS ändert an ihnen nichts und übernimmt sie unverändert aus den
offiziellen Paketquellen.

## Wichtige Bestandteile

| Bestandteil | Lizenz | Quellcode |
|---|---|---|
| Linux-Kernel (Raspberry Pi) | GPL-2.0 | https://github.com/raspberrypi/linux |
| Kodi (Paket aus Debian/Raspberry Pi) | GPL-2.0-or-later | https://github.com/xbmc/xbmc |
| Plymouth | GPL-2.0-or-later | https://gitlab.freedesktop.org/plymouth/plymouth |
| Chromium | BSD-3-Clause und weitere | https://chromium.googlesource.com/chromium/src |
| systemd, NetworkManager, GNU-Werkzeuge u. a. | GPL / LGPL | über die Debian-Quellpakete (siehe unten) |
| Raspberry-Pi-Firmware | proprietär, frei weitergebbar | https://github.com/raspberrypi/firmware |

Die vollständige Liste aller Pakete mit Versionen liegt jedem Release als
`.info`-Datei bei. Auf einem laufenden System zeigt `dpkg -l` dieselbe Liste;
die Lizenztexte jedes Pakets stehen unter `/usr/share/doc/<paket>/copyright`.

## Quellcode der enthaltenen Pakete

- Debian-Pakete: https://sources.debian.org und https://deb.debian.org/debian/pool/
- Pakete aus dem Raspberry-Pi-Archiv: https://archive.raspberrypi.com/debian/pool/
- Auf einem Debian-System: `apt-get source <paketname>` (nach Aktivieren der `deb-src`-Quellen)

## Nicht enthalten: Widevine

Das DRM-Modul **Widevine** (`libwidevinecdm0`, für Netflix, Prime Video, Disney+ u. a.)
ist keine freie Software. Es ist **nicht** Teil des Echo-OS-Images, sondern wird beim
ersten Start direkt aus der offiziellen Raspberry-Pi-Paketquelle installiert und
unterliegt den Bedingungen seines Anbieters.

## Marken

„Kodi“ ist eine Marke der XBMC Foundation. Echo-OS ist ein eigenständiges Projekt,
nutzt Kodi unverändert („Powered by Kodi“) und steht in keiner Verbindung zur
XBMC Foundation; es wird von ihr weder unterstützt noch empfohlen.
„Raspberry Pi“ ist eine Marke von Raspberry Pi Ltd. Namen von Streamingdiensten
werden nur genannt, um auf die jeweiligen Angebote zu verweisen; Echo-OS enthält
keine Logos dieser Dienste und keine Inhalte Dritter.

## Echo-OS-eigene Bestandteile

Build-Skripte, Einrichtungsdienste, KI-Agent, Kodi-Addon „Streaming“ und Bootscreen:
Quellcode unter https://github.com/EchoWP-Design/echo-os
