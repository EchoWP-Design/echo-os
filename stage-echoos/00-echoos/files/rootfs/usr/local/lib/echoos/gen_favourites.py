#!/usr/bin/env python3
"""Schreibt Kodi-Favoriten für alle Streaming-Apps (erscheinen im Hauptmenü
unter "Favoriten")."""
import json
from xml.sax.saxutils import escape, quoteattr

SERVICES = "/usr/share/echoos/services.json"
TILES = "/usr/share/echoos/tiles"

with open(SERVICES, encoding="utf-8") as fh:
    services = json.load(fh)

print("<favourites>")
for svc in services:
    sid = svc["id"]
    cmd = 'RunPlugin("plugin://plugin.program.echoos.streaming/?launch=%s")' % sid
    thumb = "%s/%s.png" % (TILES, sid)
    print("    <favourite name=%s thumb=%s>%s</favourite>"
          % (quoteattr(svc["name"]), quoteattr(thumb), escape(cmd)))
print("</favourites>")
