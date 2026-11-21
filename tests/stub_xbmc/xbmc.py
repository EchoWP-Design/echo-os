"""Test-Attrappe für Kodis Modul xbmc. Verhalten über Umgebungsvariablen:
XBMC_STUB_PLATFORM=android, XBMC_STUB_APPS=<JSON-Liste [[paket, name], …]>, XBMC_STUB_LOG=<Protokolldatei>."""
import json
import os

from xbmcgui import _log


def sleep(ms):
    pass


def log(msg, level=0):
    print("xbmc.log:", msg)


def executebuiltin(cmd):
    _log("builtin", command=cmd)


def getCondVisibility(cond):
    if cond == "System.Platform.Android":
        return os.environ.get("XBMC_STUB_PLATFORM") == "android"
    return False


def executeJSONRPC(request):
    req = json.loads(request)
    if req.get("method") == "Files.GetDirectory" and req["params"]["directory"].startswith("androidapp://"):
        apps = json.loads(os.environ.get("XBMC_STUB_APPS", "[]"))
        files = [{"file": f"androidapp://sources/apps/{p}", "label": l, "filetype": "file"} for p, l in apps]
        return json.dumps({"id": req.get("id"), "jsonrpc": "2.0", "result": {"files": files}})
    return json.dumps({"id": req.get("id"), "jsonrpc": "2.0", "error": {"code": -32601}})
