import json
import time

import xbmc
import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")

def log(msg):
    xbmc.log(f"[{ADDON_ID}] {msg}", xbmc.LOGINFO)

def get_int_setting(key, default):
    try:
        return int(ADDON.getSetting(key))
    except Exception:
        return default

def get_bool_setting(key, default):
    try:
        v = (ADDON.getSetting(key) or "").lower().strip()
        return v in ("true", "1", "yes", "on")
    except Exception:
        return default

def is_enabled():
    return get_bool_setting("enabled", True)

def get_action_method():
    # select stores index as string: 0..3
    try:
        idx = int(ADDON.getSetting("action"))
    except Exception:
        idx = 0

    return {
        0: "System.Shutdown",
        1: "System.Suspend",
        2: "System.Hibernate",
        3: "Application.Quit",
    }.get(idx, "System.Shutdown")

def jsonrpc(method):
    req = {"jsonrpc": "2.0", "id": 1, "method": method}
    return xbmc.executeJSONRPC(json.dumps(req))

def is_screensaver_active():
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "XBMC.GetInfoBooleans",
        "params": {"booleans": ["System.ScreenSaverActive"]},
    }
    raw = xbmc.executeJSONRPC(json.dumps(req))
    try:
        data = json.loads(raw)
        return bool(data["result"]["System.ScreenSaverActive"])
    except Exception:
        return False

class Monitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.screensaver_started_at = None

    def onNotification(self, sender, method, data):
        # If disabled, ignore and ensure timer is cleared
        if not is_enabled():
            self.screensaver_started_at = None
            return

        if method == "GUI.OnScreensaverActivated":
            self.screensaver_started_at = time.time()
            log("Screensaver activated; countdown started.")
        elif method == "GUI.OnScreensaverDeactivated":
            if get_bool_setting("cancel_on_deactivate", True):
                self.screensaver_started_at = None
                log("Screensaver deactivated; countdown cancelled.")

    def onSettingsChanged(self):
        # Fired when user changes any setting, including pressing action buttons.
        # For type="action", Kodi triggers this callback when activated.
        try:
            test = (ADDON.getSetting("test_action") or "").lower().strip()
        except Exception:
            test = ""

        if test:
            # Some skins store "true"/"1" transiently; treat any non-empty as pressed.
            method = get_action_method()
            log(f"Test button pressed; executing {method}.")
            jsonrpc(method)

            # Attempt to reset the action setting back to empty to avoid re-trigger loops.
            try:
                ADDON.setSetting("test_action", "")
            except Exception:
                pass

def run():
    mon = Monitor()
    log("Service started.")

    while not mon.abortRequested():
        if not is_enabled():
            mon.screensaver_started_at = None
            if mon.waitForAbort(2):
                break
            continue

        delay_minutes = get_int_setting("delay_minutes", 5)
        delay_seconds = max(60, delay_minutes * 60)
        action_method = get_action_method()

        if mon.screensaver_started_at is not None:
            elapsed = time.time() - mon.screensaver_started_at
            if elapsed >= delay_seconds:
                if is_screensaver_active():
                    log(f"Screensaver active for {delay_minutes} min; executing {action_method}.")
                    jsonrpc(action_method)
                else:
                    log("Timer elapsed but screensaver not active; ignoring.")
                mon.screensaver_started_at = None

        if mon.waitForAbort(2):
            break

    log("Service stopped.")

if __name__ == "__main__":
    run()