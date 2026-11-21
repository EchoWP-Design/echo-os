"""Attrappe: special://home/ wird auf XBMC_STUB_HOME abgebildet."""
import os
def translatePath(path):
    if path.startswith("special://home/"):
        return os.path.join(os.environ.get("XBMC_STUB_HOME", "/tmp/xbmc-home"), path[len("special://home/"):])
    return path
