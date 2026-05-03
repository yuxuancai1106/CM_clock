"""Arduino bridge for The Clock.

Polls the Flask server's /state endpoint. Whenever the clock's state changes,
it emits a single-line command (default: prints to stdout). When you wire up
the Arduino, you uncomment a few lines at the bottom to send that same line
over USB serial.

Wire format (one ASCII line per state change, newline-terminated):

    STATE <name>\\n

where <name> is one of:
    neutral at_ease joyful surprised anxious embarrassed angry

The Arduino just needs to read lines from Serial and switch its OLED face,
motor pose, and speaker cue based on the name.

Usage:
    # in one terminal:
    python app.py

    # in another terminal:
    python bridge.py                                 # prints commands only
    python bridge.py --serial /dev/tty.usbmodemXXXX  # also sends to Arduino
    python bridge.py --url http://192.168.1.50:5050  # if running on another box
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from urllib import error as urlerror
from urllib import request as urlrequest


def fetch_state(url: str) -> dict | None:
    try:
        with urlrequest.urlopen(url + "/state", timeout=4) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urlerror.URLError, TimeoutError, json.JSONDecodeError):
        return None


def open_serial(device: str, baud: int):
    """Lazy-import pyserial so this script still works if it isn't installed."""
    try:
        import serial  # type: ignore
    except ImportError:
        print("[bridge] pyserial not installed. run: pip install pyserial", file=sys.stderr)
        sys.exit(1)
    return serial.Serial(device, baudrate=baud, timeout=1)


def emit(line: str, ser=None) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()
    if ser is not None:
        ser.write((line + "\n").encode("ascii"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge clock state to Arduino")
    parser.add_argument("--url",     default="http://localhost:5050",
                        help="Flask server base URL (default: http://localhost:5050)")
    parser.add_argument("--serial",  default=None,
                        help="Serial device path (e.g. /dev/tty.usbmodem1101). Omit to print only.")
    parser.add_argument("--baud",    type=int, default=115200,
                        help="Serial baud rate (default: 115200)")
    parser.add_argument("--poll",    type=float, default=0.5,
                        help="Polling interval in seconds (default: 0.5)")
    args = parser.parse_args()

    ser = open_serial(args.serial, args.baud) if args.serial else None
    if ser is not None:
        # Many Arduinos auto-reset on serial open — give the bootloader time.
        time.sleep(2.0)
        print(f"[bridge] connected to {args.serial} @ {args.baud} baud", file=sys.stderr)

    print(f"[bridge] polling {args.url}/state every {args.poll}s. ctrl-c to stop.", file=sys.stderr)

    last_state: str | None = None
    last_version: int | None = None

    while True:
        state = fetch_state(args.url)
        if state is None:
            time.sleep(args.poll)
            continue

        s = state.get("state")
        v = state.get("version")

        if s != last_state:
            emit(f"STATE {s}", ser)
            last_state = s

        last_version = v
        time.sleep(args.poll)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[bridge] bye.", file=sys.stderr)
