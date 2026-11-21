# Echo-App – App-Symbol (Stand 21.11.2026)

Grundlage: rundes Elefanten-Logo (schriftzug/entwurf-01/rund/rund-elefant), Gelb #FFD400 auf Schwarz #0A0A0A. Bauweise wie EchoWP-Mail/Newsflash; Produktzeichen am Echo-Bogen: **Fernbedienung** (Variante B, von Jan gewählt) – Echo-App steuert Fire TV und später den Echo-OS-Pi.

| Datei | Zweck |
|---|---|
| echo-app_symbol_rund.svg / _1024.png | Hauptsymbol (runder schwarzer Kreis): ältere Launcher, Webseite, GitHub |
| echo-app_android-vordergrund.svg / _1024.png | Android Adaptive Icon, Vordergrund (transparent; Hintergrund #0A0A0A); Motiv bis Radius 284 px, in der Sicherheitszone |
| echo-app_android-monochrom.svg / _1024.png | Android 13+ Themensymbole (einfarbig) |
| echo-app_tv-symbol_1024.png | Fernseher (Fire TV, Android TV): quadratisches Symbol mit dem Banner-Motiv (Elefant + „Echo App“). Fire TV zeigt bei Apps außerhalb des Amazon Appstore kein Banner und vergrößert Adaptive Icons zu stark; Android wählt dieses Bild über `mipmap-television-*` automatisch |
| echo-app_store_512.png | Store-/Profilbild, quadratisch |
| echo-app_tv-banner_320x180.png | Fire-TV-/Android-TV-Banner: Elefant + Wortmarke „Echo“ mit Block „App“ (Inter Display Black) |
| 00_uebersicht-launcher.png | Vorschau: runde Maske, abgerundete Maske, 48 px, Banner |
| generator-echo-app.py | erzeugt alle Dateien neu (Python, cairosvg, Pillow, Inter Display Black) |

Im Repo `EchoWP-Design/echo-os` unter `app/branding/`; `app/tool/patch_android.py` baut daraus die Android-Symbole.
