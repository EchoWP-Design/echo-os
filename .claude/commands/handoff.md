---
description: Sitzung sauber übergeben – schreibt HANDOFF.md, damit eine neue Sitzung nahtlos weitermacht
---

Schreibe den aktuellen Arbeitsstand in `HANDOFF.md` im Wurzelverzeichnis des Repos. Überschreibe eine vorhandene Datei vollständig, ältere Übergaben werden nicht aufbewahrt. Die Datei ist für eine neue Claude-Sitzung ohne Vorwissen gedacht: knapp, konkret, auf Deutsch.

Aufbau (genau diese Abschnitte, leere Abschnitte mit „–“):

```markdown
# Übergabe – <Datum JJJJ-MM-TT, Uhrzeit>

## Ziel der Sitzung
Ein bis zwei Sätze: woran gearbeitet wurde und warum.

## Erledigt
- Änderung – Datei(en) – Commit-Hash, falls committet

## Offen / nächster Schritt
1. Der konkret nächste Schritt (womit die neue Sitzung anfängt)
2. …

## Entscheidungen
- Was festgelegt wurde und der Grund (nur, was nicht schon in README/Projektakte steht)

## Bekannte Probleme
- Fehler, Fehlschläge, Sackgassen – mit dem, was schon versucht wurde

## Zustand
- Branch, letzter Commit, nicht committete Änderungen (`git status` kurz)
- Letzter Build-/Testlauf und Ergebnis
```

Regeln:
- Keine Schlüssel, Passwörter, Tokens, Keystore-Passwörter oder persönliche Daten – das Repo kann öffentlich sein.
- Nichts wiederholen, was in README.md oder einer Projektakte (z. B. PROJEKT.md) steht; dort verweisen.
- Höchstens ca. 60 Zeilen.
- Danach `HANDOFF.md` committen mit der Nachricht `Übergabe: <Kurzthema> [skip ci]` und pushen, damit eine Sitzung auf einem anderen Gerät sie findet.
- Zum Schluss Jan in einem Satz sagen, dass er jetzt eine neue Sitzung starten kann, und die Zeile für den Einstieg nennen: „Lies HANDOFF.md und mach beim nächsten Schritt weiter.“
