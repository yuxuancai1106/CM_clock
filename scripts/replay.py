"""Fire a scripted conversation at the running Flask server.

Use this to verify the state machine end-to-end without typing in the browser.
Shows the resolved state and the clock's reaction for each message.

Usage:
    python scripts/replay.py
    python scripts/replay.py --url http://localhost:5050 --delay 1.5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from urllib import error as urlerror
from urllib import request as urlrequest

# Each step is (delay-before, message). delay=None means "send immediately".
SCRIPT: list[tuple[float, str]] = [
    (0.0,  "hello clock"),                         # other -> neutral (after surprise)
    (4.0,  "captions are not working"),            # problem (new) -> anxious
    (4.0,  "subtitles are still missing"),         # same problem -> embarrassed
    (4.0,  "captions still gone, please fix"),     # same again -> angry
    (4.0,  "thank you so much for trying"),        # gratitude -> joyful + reset
    (4.0,  "the wifi is dead"),                    # new problem -> anxious
]


def post(url: str, text: str) -> dict:
    body = json.dumps({"text": text}).encode("utf-8")
    req = urlrequest.Request(
        url + "/message",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlrequest.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url",   default="http://localhost:5050")
    ap.add_argument("--delay", type=float, default=None,
                    help="Override per-step delay; otherwise uses the script's own.")
    args = ap.parse_args()

    print(f"replaying scripted conversation against {args.url}\n")
    for i, (default_delay, msg) in enumerate(SCRIPT, 1):
        delay = args.delay if args.delay is not None else default_delay
        if delay > 0:
            time.sleep(delay)
        try:
            data = post(args.url, msg)
        except urlerror.URLError as e:
            print(f"  ! could not reach server: {e}")
            sys.exit(1)
        m = data["message"]
        st = data["state"]["state"]
        print(f"[{i}] you   > {msg}")
        print(f"    clock < {m['reaction']!r:35}  state={st:<11} settles_to={m['settles_to']:<11} intent={m['intent']:<9} topic={m['topic']!r}")
        print()


if __name__ == "__main__":
    main()
