"""ClockBrain — the orchestrator and time-driven layer.

Responsibilities (everything else now lives in emotion.py):

  - Keep a short rolling history of recent messages so the classifier can do
    "this is the same problem the user mentioned earlier".
  - Apply the SURPRISE FLASH on the first message after silence.
  - Apply the IDLE -> at_ease transition after long quiet.
  - Pick a short reply aimed at the person texting: validation, apologies,
    and calm reassurance when they are upset—not the clock performing anger back.
  - Hand the resolved state out via /state to the page and to bridge.py.

The states `surprised` and `at_ease` are owned here (time-driven). The other
five (`neutral`, `joyful`, `anxious`, `embarrassed`, `angry`) come straight
from the classifier — we trust the LLM to read tone and detect repeats.
"""

from __future__ import annotations

import random
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any

from emotion import Classification, classify

STATES: tuple[str, ...] = (
    "neutral",
    "at_ease",
    "joyful",
    "surprised",
    "anxious",
    "embarrassed",
    "angry",
)

# ---- tunables -------------------------------------------------------------
SURPRISE_FLASH_SECONDS = 3.0
# A message only triggers the surprise flash if the previous message was MORE
# than this long ago. With this set to 600s (== idle threshold), the flash
# fires on the very first message after a 10-minute quiet period — i.e.
# when the clock is "snapping out of at_ease".
QUIET_BEFORE_SURPRISE = 10 * 60
IDLE_AT_EASE_SECONDS = 10 * 60
HISTORY_MAXLEN = 30                # messages kept in memory for LLM + dev panel
HISTORY_FOR_LLM = 8                # how many we feed into the prompt

# Each line speaks *to the user*. Classifier labels like "angry" mean *they*
# sound furious; our text stays gentle and apologetic, never snapping at them.
_REACTIONS: dict[str, tuple[str, ...]] = {
    "neutral": (
        "i'm here--go ahead.",
        "i'm listening.", "steady. tell me more.",
        "take your time.", "okay. what's up?",
    ),
    "at_ease": (
        "it's quiet again--i'm glad you're still here.", "no rush.",
        "resting together for a beat.", "i'll be right here when you're ready.",
    ),
    "joyful": (
        "thank you--that means a lot.", "you're kind to say so.",
        "that really helps--thank you.", "i appreciate you.", "that's so generous of you.",
    ),
    "surprised": (
        "oh--okay.", "that's a lot--i'm listening.",
        "okay--i caught that.", "i'm with you. keep going.", "i'm tracking. go on.", "hang on--i'm with you.",
    ),
    "anxious": (
        "i'm sorry that's happening.", "that's really frustrating--i'm sorry.",
        "i hear you. that shouldn't feel broken.", "you're right to say something.",
        "ugh--i'm sorry it's like that.", "thank you for telling me.", "okay. i hear the stress in that.",
    ),
    "embarrassed": (
        "i'm really sorry you're still hitting this.", "you shouldn't have to repeat yourself--sorry.",
        "that's on us--thank you for your patience.", "i owe you another sorry--still not right.",
        "you deserve better than this loop.", "that's embarrassing for me too--sorry.",
    ),
    "angry": (
        "you sound really stretched thin--i'm sorry.", "i hear you're at your limit.", "okay. i'm not blaming you.", "that's fair frustration--i'm sorry.", "slow down whenever you want--i'm listening.",
        "i'm not taking it personally--i know you're upset.", "breathe if you need. i'm still here.",
        "i'm sorry this kept pushing you.", "you're not wrong to be upset.", "tell me calmly when you're ready--i'll wait.",
    ),
}


@dataclass
class BrainSnapshot:
    state: str
    reaction: str
    meta: dict[str, Any]
    version: int


class ClockBrain:
    """Thread-safe orchestrator. Call `process_message(text)` per inbound msg
    and `snapshot()` whenever you want the current resolved state."""

    def __init__(self, now: float | None = None) -> None:
        self._lock = threading.Lock()
        now = now if now is not None else time.time()
        self._created_at = now
        self._last_message_at: float | None = None

        # Surprise flash bookkeeping
        self._surprise_until: float | None = None
        self._pending_state: str | None = None

        # Currently resolved (post-flash) state
        self._resolved_state = "neutral"
        self._resolved_reaction = random.choice(_REACTIONS["neutral"])

        # Rolling message history (newest at the right)
        self._history: deque[dict] = deque(maxlen=HISTORY_MAXLEN)

        self._version = 0

    # ----------------------------------------------------------------- core

    def process_message(self, text: str, now: float | None = None,
                        msg_id: str | None = None) -> dict:
        """Classify a new message (using history for context), then update
        the brain. Returns the canonical history entry plus a `current` field
        for the immediate state (which may be `surprised` if the flash is
        active). `msg_id` lets the client provide a stable id so polling and
        the POST response dedupe to the same row."""
        now = now if now is not None else time.time()

        # Snapshot history outside the lock — the LLM call may be slow.
        with self._lock:
            history_for_llm = list(self._history)[-HISTORY_FOR_LLM:]

        classification = classify(text, history_for_llm)

        with self._lock:
            self._tick_locked(now)

            target = classification.state
            reaction = random.choice(_REACTIONS[target])

            # Decide: do we flash surprised first?
            quiet_long_enough = (
                self._last_message_at is None
                or (now - self._last_message_at) >= QUIET_BEFORE_SURPRISE
            )

            if quiet_long_enough:
                self._surprise_until = now + SURPRISE_FLASH_SECONDS
                self._pending_state = target
            else:
                self._surprise_until = None
                self._pending_state = None
            self._resolved_state = target
            self._resolved_reaction = reaction

            entry = {
                "id": msg_id or uuid.uuid4().hex,
                "text": text,
                "state": target,
                "topic": classification.topic,
                "reaction": reaction,
                "ts": now,
                "flashed_surprise": quiet_long_enough,
            }
            self._history.append(entry)

            self._last_message_at = now
            self._version += 1

            return {
                **entry,
                "current": "surprised" if quiet_long_enough else target,
                "settles_to": target,
            }

    # ----------------------------------------------------------------- read

    def snapshot(self, now: float | None = None) -> BrainSnapshot:
        now = now if now is not None else time.time()
        with self._lock:
            self._tick_locked(now)
            current = self._current_state_locked(now)
            reaction = (
                random.choice(_REACTIONS["surprised"])
                if current == "surprised"
                else self._resolved_reaction
            )
            return BrainSnapshot(
                state=current,
                reaction=reaction,
                meta={
                    "settles_to": self._pending_state or self._resolved_state,
                    "history": list(self._history),
                    "seconds_since_last_message": (
                        round(now - self._last_message_at, 1)
                        if self._last_message_at is not None else None
                    ),
                    "idle_threshold": IDLE_AT_EASE_SECONDS,
                    "quiet_before_surprise": QUIET_BEFORE_SURPRISE,
                    "surprise_flash_seconds": SURPRISE_FLASH_SECONDS,
                },
                version=self._version,
            )

    def messages(self, limit: int | None = None) -> list[dict]:
        """Return a copy of recent messages (oldest first)."""
        with self._lock:
            data = list(self._history)
        return data if limit is None else data[-limit:]

    # ----------------------------------------------------------------- internals

    def _tick_locked(self, now: float) -> None:
        # Surprise flash expiration
        if self._surprise_until is not None and now >= self._surprise_until:
            if self._pending_state is not None:
                self._resolved_state = self._pending_state
            self._surprise_until = None
            self._pending_state = None
            self._version += 1

        # Idle drift
        if (
            self._last_message_at is not None
            and (now - self._last_message_at) >= IDLE_AT_EASE_SECONDS
            and self._resolved_state != "at_ease"
        ):
            self._resolved_state = "at_ease"
            self._resolved_reaction = random.choice(_REACTIONS["at_ease"])
            self._version += 1

    def _current_state_locked(self, now: float) -> str:
        if self._surprise_until is not None and now < self._surprise_until:
            return "surprised"
        return self._resolved_state
