#!/usr/bin/env python3
"""Beendet die Streaming-App (zurück zu Kodi) bei Home-Taste, F12,
EXIT-Taste oder wenn ESC/Zurück 1,5 Sekunden gehalten wird."""
import select
import subprocess
import time

import evdev
from evdev import ecodes

EXIT_KEYS = {ecodes.KEY_HOMEPAGE, ecodes.KEY_F12, ecodes.KEY_EXIT}
HOLD_KEYS = {ecodes.KEY_ESC, ecodes.KEY_BACK}
HOLD_SECONDS = 1.5


def quit_app():
    subprocess.run(["pkill", "-TERM", "-x", "cage"], check=False)
    raise SystemExit(0)


def main():
    devices = []
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
            if ecodes.EV_KEY in dev.capabilities():
                devices.append(dev)
        except OSError:
            pass
    if not devices:
        return
    fds = {dev.fd: dev for dev in devices}
    held_since = None
    while True:
        ready, _, _ = select.select(fds, [], [], 0.3)
        for fd in ready:
            try:
                events = list(fds[fd].read())
            except OSError:
                continue
            for ev in events:
                if ev.type != ecodes.EV_KEY:
                    continue
                if ev.code in EXIT_KEYS and ev.value == 1:
                    quit_app()
                if ev.code in HOLD_KEYS:
                    if ev.value == 1:
                        held_since = time.monotonic()
                    elif ev.value == 0:
                        held_since = None
        if held_since and time.monotonic() - held_since >= HOLD_SECONDS:
            quit_app()


if __name__ == "__main__":
    main()
