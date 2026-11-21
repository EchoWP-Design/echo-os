# Echo-OS – Projektakte

Stand: Version 1.0 (1. November 2026), Android-Ausbau seit 21. November 2026 (Schritt 1: Kodi-Addon fertig). Diese Datei fasst zusammen, wie Echo-OS aufgebaut ist,
warum es so gebaut ist und was beim ersten echten Einsatz gelernt wurde – damit die Arbeit
jederzeit, auch in einem neuen Chat mit Claude, nahtlos weitergehen kann.

## Ziel
Media-Center-Betriebssystem für Raspberry Pi 4/5: Neon-Bootscreen im 80er-Stil, Kodi als
Oberfläche, Streaming-Apps als Kacheln, automatische Laufwerkserkennung, KI-Agent „ECHO“,
der das System steuert und Updates/Sicherheit überwacht. Flashbar mit balenaEtcher.

## Aufbau
| Teil | Datei(en) | Aufgabe |
|---|---|---|
| Build | `config`, `build.sh`, `.github/workflows/build.yml` | pi-gen (arm64, Debian 13 Trixie) baut `stage0–2` + `stage-echoos`; Image `.img.xz` |
| Pakete | `stage-echoos/00-echoos/00-packages` | Kodi, cage, Chromium, Plymouth, nftables, fail2ban … (kein Widevine) |
| Einrichtung im Image | `01-run.sh` (Host), `02-run-chroot.sh` (chroot) | Dateien kopieren, Rechte, Dienste aktivieren, Bootscreen erzeugen |
| Einstellungen | `files/boot/echoos.conf` → `usr/local/lib/echoos/echoos_config.py` | läuft bei jedem Start vor Kodi; übernimmt WLAN, Passwort, SSH, API-Schlüssel; löscht Geheimnisse aus der Datei |
| Bootscreen | `usr/local/lib/echoos/gen_bootscreen.py`, `usr/share/plymouth/themes/echo/echo.script` | Grafiken werden beim Build erzeugt; Plymouth-Skript animiert Gitter, Logo, Lichtspur |
| Kodi | `home/echoos/.kodi/…`, `etc/systemd/system/kodi.service` | kodi-standalone auf tty1 (GBM), JSON-RPC lokal auf 9090 |
| Streaming | `usr/share/echoos/services.json`, Addon `plugin.program.echoos.streaming`, `usr/local/bin/echoos-browser`, `echoos-browser@.service` | Chromium-Kiosk in cage; Kodi wird per `Conflicts=` beendet und danach neu gestartet |
| Laufwerke | `etc/udev/rules.d/99-echoos-automount.rules`, `automount.sh` | hängt Datenträger unter `/media/<Label>` ein (systemd-mount, Fallback mount) |
| KI-Agent | `opt/echoos/agent/echoos_agent.py`, `web/index.html` | Web-UI Port 8090, Claude-API mit Tool-Use, Bibliothekszuordnung, Update-/Sicherheitsmonitor |
| DRM | `echoos-widevine.service`, `install_widevine.sh` | installiert Widevine beim ersten Start aus der Raspberry-Pi-Quelle |
| Sicherheit | `etc/nftables.conf`, `fail2ban`, `unattended-upgrades` | nur Heimnetz, SSH nur mit Schlüssel, sudo nur mit Passwort |
| Lizenzen | `usr/share/doc/echoos/LIZENZEN.md` | auch als `LIZENZEN.txt` auf bootfs und am Release |
| Tests | `tests/` | `test_all.py` (63 Funktionstests), `run_ui_demo.sh`, `ci_visual_test.sh` (echtes Plymouth + Kodi), `addon_visual_test.sh` (Addon in echtem Kodi), `vm/` (QEMU) |
| Android-Addon | `tools/build_kodi_addon.py`, Addon-Ordner `resources/lib/echostream.py`, `service.py` | baut `plugin.program.echoos.streaming-<version>.zip` mit Kacheln, Startbild und `services.json` |

## Wichtige Entscheidungen
- **Basis Raspberry Pi OS statt eigenem Kernel:** Sicherheitsupdates kommen weiter aus Debian/Raspberry Pi.
- **Streaming über Chromium-Kiosk statt Kodi-Addons:** einheitlich für alle Dienste, Widevine von Raspberry Pi.
- **Kacheln ohne Logos:** nur Name und Farbe (Marken-/Urheberrecht).
- **Widevine nicht im Image:** proprietär; Installation beim ersten Start.
- **Repository öffentlich:** kostenloser ARM-Build und Release-Speicher; keine persönlichen Daten im Repo.

## Android-Ausbau (ab v1.1)
Drei Schritte, nacheinander:
1. **Echo Streaming als Kodi-Addon für Android** (fertig, Addon 1.1.0): dasselbe Addon wie auf dem Pi. Auf Android öffnen die Kacheln die installierte App per `StartAndroidActivity(<paket>)`, fehlt sie, den Play Store (`market://`) bzw. Amazon Appstore (`amzn://`). Installierte Apps liest das Addon per JSON-RPC aus `androidapp://sources/apps/`. Paketnamen je Dienst für TV und Handy stehen in `services.json` (`android.tv` / `android.mobile`). Ein Addon-Dienst legt den Neon-Startbildschirm als `special://home/media/splash.jpg` ab (nur eigene Kopie, abschaltbar). Logik ohne Kodi-Abhängigkeit in `resources/lib/echostream.py`, testbar. ZIP: `tools/build_kodi_addon.py`; der Build-Workflow hängt es an jedes Release.
2. **Echo-App, TV-Modus** (in Arbeit, Jans Gerät: Fire TV mit Fire OS 7.7 = Android 9): Flutter-App in `app/` mit Neon-Intro (Grafiken aus `gen_bootscreen.py`), Kacheln (`gen_tiles.py`, Paketlogik wie `echostream.py`), Kodi-Start (`org.xbmc.kodi`) und ECHO-Chat (Pi-Agent bevorzugt, sonst Claude direkt mit eigenem Schlüssel; Code/Schlüssel in flutter_secure_storage). Kein Ersatz-Startbildschirm (Fire TV blockiert das; Umgehungen schalten Updates ab). `android/` entsteht in CI per `flutter create`, `tool/patch_android.py` ergänzt Leanback, Banner, HTTP im Heimnetz, MainActivity (Kanal `echoos/apps`) und Signatur. Workflow `.github/workflows/app.yml`; ohne Secrets `ECHO_APP_KEYSTORE_B64`/`ECHO_APP_KEYSTORE_PASSWORD` entsteht nur `EchoApp-Test.apk`. Lokal kein Flutter (Google-Server gesperrt) – Patch-Skript wurde gegen die echten Flutter-Vorlagen von GitHub geprüft.
3. **Echo-App, Handy-Modus** (geplant): dieselbe APK als Fernbedienung für den Agenten auf dem Pi (`/api/status`, `/api/chat`, `/api/action`, Bearer-Code, nur Heimnetz).

## Beim ersten echten Start gelernt (alle behoben)
1. **Einrichtung hing:** `systemctl enable --now ssh` aus einem Dienst mit `Before=ssh.service` wartete auf sich selbst → Kodi und Agent starteten nie. Jetzt `start --no-block` + `TimeoutStartSec=3min`.
2. **WLAN nach Neustart weg:** Passwort wurde (gewollt) aus `echoos.conf` gelöscht, die Verbindung dann ohne Passwort neu angelegt. Jetzt bleibt eine bestehende Verbindung unangetastet.
3. **Kodi fragte „Add-on aktivieren?“:** Addons werden vor dem ersten Kodi-Start in `Addons33.db` aktiviert.
4. **Ohne eigenes Passwort kein sudo:** Echo-OS setzt dann ein Zufallspasswort. Für SSH-Wartung in `echoos.conf` ein Passwort vergeben.
5. **Zugangscode verpasst:** Knopf „Code auf dem Fernseher anzeigen“ auf der Anmeldeseite.
6. **Uploads von Windows verlieren das Ausführungsrecht:** Workflows setzen es per `chmod`; `.gitattributes` erzwingt LF.
7. **QEMU zeigt keinen Bootscreen:** QEMU emuliert die Pi-Grafik (vc4/KMS) nicht; auf echter Hardware funktioniert er.

## Arbeitsabläufe
- **Image bauen:** GitHub → Actions → Build Echo-OS → Run workflow (ca. 10 min). Lokal: `./build.sh` (Docker).
- **Release:** Releases → Draft a new release → neues Tag (`v1.1` …) → Publish; der Build hängt Image, Prüfsumme, Paketliste und Lizenzen an.
- **Tests:** `python3 tests/test_all.py` (63); `bash tests/addon_visual_test.sh` für das Addon in echtem Kodi (wartet per `Container.NumItems`, bis alle Kacheln geladen sind – feste Wartezeit war unter Software-Rendering zu kurz); auf GitHub automatisch bei jedem Push.
- **Wartung am Pi:** `ssh echoos@<IP>`; Protokolle mit `journalctl -u kodi`, `journalctl -u echoos-agent`, `journalctl -u echoos-config`.

## Ideen für später
- Startbildschirm-Kachelreihe für Streaming direkt im Kodi-Hauptmenü (eigenes Skin-Widget)
- Sprachsteuerung für ECHO
- Deutsche Kodi-Oberfläche und TMDb-Sprache automatisch auf Deutsch
- Lizenz für die Echo-OS-eigenen Teile festlegen (z. B. MIT oder GPL)
