#!/usr/bin/env python3
"""Poll Flask GET /state and forward `state` to the MCU (Arduino App Lab Bridge).

Configured for this repo's Flask API (see ../../app.py):
  GET  {SERVER_BASE}/state  →  JSON top-level keys "state", "version", ...

Arduino Lab runtime may inject ``Bridge``. When developing on a laptop without
hardware, we fall back to printing lines you can optionally pipe to Serial:

    STATE joyful\\n

Edit SERVER_BASE below (scheme + host + optional port — NO trailing slash).
"""

from __future__ import annotations

import json
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

# -----------------------------------------------------------------------------
# Flask base URL — must reach the SAME server as your browser chat UI.
#
# Examples:
#   SERVER_BASE = "http://192.168.68.53:5050"
#   SERVER_BASE = "https://YOUR-NGROK.ngrok-free.app"
# -----------------------------------------------------------------------------
SERVER_BASE = "http://127.0.0.1:5050"

POLL_INTERVAL_S = 0.5


def _fetch_state() -> dict | None:
    url = SERVER_BASE.rstrip("/") + "/state"
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=8) as resp:
            raw = resp.read().decode()
        return json.loads(raw)
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        print("[python] GET failed:", e, file=sys.stderr)
        return None


try:
    from Bridge import Bridge  # type: ignore  # provided by Arduino App Lab

    _HAVE_BRIDGE = True
except ImportError:

    class _StubBridge:
        @staticmethod
        def call(cmd: str, arg: str) -> None:
            print(f"[python] Bridge.call({cmd!r}, {arg!r})")

    Bridge = _StubBridge()
    _HAVE_BRIDGE = False


def notify_sketch(emotion: str) -> None:
    Bridge.call("set_state", emotion)
    # Optional: mirror bridge.py protocol for UART bring-up tools
    if not _HAVE_BRIDGE:
        sys.stdout.write("STATE " + emotion + "\n")
        sys.stdout.flush()


def main() -> None:
    print("[python] Polling:", SERVER_BASE + "/state", flush=True)
    last_emotion = None

    while True:
        payload = _fetch_state()
        if isinstance(payload, dict):
            emotion = str(payload.get("state", "") or "").strip()
            ver = payload.get("version")
            if emotion and emotion != last_emotion:
                print("[python]", ver, "→", emotion, flush=True)
                notify_sketch(emotion)
                last_emotion = emotion
        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[python] stopped.", flush=True)
