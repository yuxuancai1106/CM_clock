"""Clock chat — a webpage where attendees text a sentient clock.

Run:
    pip install -r requirements.txt
    python app.py

Endpoints:
  GET  /          - the chat page
  POST /message   - submit a user message; returns the immediate reaction
  GET  /state     - current clock state (cheap; safe to poll)
  GET  /health    - liveness check
"""

from __future__ import annotations

import os
from typing import Any

from flask import Flask, jsonify, render_template, request

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from brain import STATES, ClockBrain

app = Flask(__name__)
brain = ClockBrain()


@app.route("/")
def index():
    return render_template(
        "index.html",
        states=list(STATES),
    )


@app.post("/message")
def post_message():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "empty message"}), 400
    if len(text) > 500:
        text = text[:500]

    client_msg_id = (data.get("client_msg_id") or "").strip() or None
    outcome = brain.process_message(text, msg_id=client_msg_id)
    snap = brain.snapshot()

    return jsonify({
        "message": outcome,    # entry already has id, text, state, topic, reaction, ts...
        "state": _state_payload(snap),
    })


@app.get("/state")
def get_state():
    return jsonify(_state_payload(brain.snapshot()))


@app.get("/health")
def health():
    return jsonify({"ok": True})


def _state_payload(snap) -> dict[str, Any]:
    return {
        "state": snap.state,
        "reaction": snap.reaction,
        "version": snap.version,
        "meta": snap.meta,
        "messages": snap.meta.get("history", []),
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=False)
