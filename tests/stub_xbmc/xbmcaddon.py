"""Attrappe: Einstellungen aus XBMC_STUB_SETTINGS (JSON), Pfade aus XBMC_STUB_ADDON_PATH / XBMC_STUB_PROFILE."""
import json, os
class Addon:
    def _s(self):
        return json.loads(os.environ.get("XBMC_STUB_SETTINGS", "{}"))
    def getSettingInt(self, key): return int(self._s().get(key, 0))
    def getSettingBool(self, key):
        defaults = {"splash": True}
        return bool(self._s().get(key, defaults.get(key, False)))
    def getAddonInfo(self, key):
        return {"path": os.environ.get("XBMC_STUB_ADDON_PATH", ""),
                "profile": os.environ.get("XBMC_STUB_PROFILE", "/tmp/xbmc-profile")}.get(key, "")
