import json, os
CALLS = os.environ.get("XBMC_STUB_LOG", "/dev/null")
def _log(kind, **kw):
    with open(CALLS, "a") as fh: fh.write(json.dumps({"call": kind, **kw}) + "\n")
NOTIFICATION_ERROR = "error"
class ListItem:
    def __init__(self, label=""): self.label = label; self.art = {}
    def setArt(self, art): self.art = art
class Dialog:
    def notification(self, heading, message, icon=None, time=0): _log("notification", heading=heading, message=message)
NOTIFICATION_WARNING = "warning"
