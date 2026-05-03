# The Clock

A texting-style webpage where attendees message a sentient clock. The clock
has a **state machine** that responds to *what* you say and *how often* you
say it, and a morphing SVG face that previews the OLED-eyes / motor / speaker
hardware that will live on the physical object.

```
user message ──▶ classifier (LLM or heuristic) ──▶ ClockBrain ──▶ state + reaction
                  ─ intent: gratitude/problem/other            ─ surprise flash
                  ─ topic:  e.g. "captions"                    ─ problem counter
                                                               ─ idle timer
```

---

## File map

| file | what it does |
| --- | --- |
| `app.py`                      | Flask web server. Routes only — `/`, `POST /message`, `GET /state`, `GET /health`. |
| `brain.py`                    | The state machine. Owns "personality": surprise flash, problem escalation, idle drift, gratitude reset. |
| `emotion.py`                  | Classifier. Turns one message into `{intent, topic}`. Heuristic by default; calls OpenAI if `OPENAI_API_KEY` is set. |
| `templates/index.html`        | Phone-frame chat shell + SVG clock skeleton + dev panel skeleton. |
| `static/style.css`            | iMessage-style theming, per-state palette, transitions, dev panel. |
| `static/app.js`               | Morphs the SVG face, renders bubbles, polls `/state`, drives the dev panel. |
| `bridge.py`                   | Polls `/state`, emits one `STATE <name>` line per change. Use it to drive the Arduino tomorrow. |
| `arduino/clock_face/clock_face.ino` | Reference Arduino sketch — listens for `STATE <name>` lines on Serial. |
| `scripts/replay.py`           | Fires a scripted conversation at the running server so you can see all states without typing. |
| `run.sh`                      | One-shot launcher: makes the venv, installs deps, starts Flask. |
| `requirements.txt`            | Python deps (Flask, python-dotenv). |
| `.env.example`                | Copy to `.env` to enable LLM mode. |

---

## Run it

```bash
# from the project root
./run.sh
```

That creates `.venv`, installs deps, and starts the server at <http://localhost:5050>.

If you'd rather do it manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

To use an LLM instead of the heuristic:

```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY=sk-...
./run.sh
```

The header status flips from `HEURISTIC` to `LLM` when the key is present.

---

## How to text and test

Open the page. You'll see three things:

1. **A phone frame** in the center — type into the iMessage-style input at the bottom.
2. **A morphing clock face** at the top of the phone — its eyes, brows, mouth, hands, blush, and aura color all change with each state.
3. **A dev panel on the right** (top-right on desktop; bottom on narrow screens). This is your testing dashboard:
   - **current state** + what it's settling into after the surprise flash
   - **active problems** with escalation tier (×1 anxious / ×2 embarrassed / ×3+ angry), color-coded
   - **last classification** — the message, intent, and extracted topic
   - **timing** — seconds since last message, idle threshold, version counter
   - **test scripts** — five buttons that fire prebuilt messages so you can hit every state in seconds
   - **raw `/state` response** — the exact JSON the Arduino will see

### Testing in 60 seconds (no typing)

Click the dev panel buttons in this order — you'll see all 7 states:

1. `report problem (anxious)` → flashes **surprised**, settles into **anxious**, problem `captions` ×1 appears
2. `repeat → embarrassed` → no flash (mid-convo), goes straight to **embarrassed**, counter ×2, blush appears
3. `repeat → angry` → **angry**, counter ×3, brows go sharp
4. `say thanks (joyful + reset)` → **joyful**, problems list clears
5. `small talk (neutral)` → **neutral**

To test idle → at_ease without waiting 10 minutes, lower `IDLE_AT_EASE_SECONDS` in `brain.py` to e.g. `30`, restart, and don't send anything for 30 seconds.

### Testing from the command line

In a second terminal (with the server running):

```bash
source .venv/bin/activate
python scripts/replay.py
```

This fires a 6-message scripted conversation and prints each resolved state.

You can also poke the API directly:

```bash
# Send a message:
curl -s localhost:5050/message -H 'Content-Type: application/json' \
     -d '{"text":"the captions are not working"}' | jq

# Get current state:
curl -s localhost:5050/state | jq
```

---

## States

| state         | when                                                             |
| ------------- | ---------------------------------------------------------------- |
| `neutral`     | default; also the resolved state after small talk                |
| `at_ease`     | no message in the last **10 minutes** (idle drift)               |
| `joyful`      | user thanked / praised the clock                                 |
| `surprised`   | flashes for **3 seconds** on the first message after a quiet gap |
| `anxious`     | a problem reported for the **first** time                        |
| `embarrassed` | the **same** problem reported a **second** time                  |
| `angry`       | the **same** problem reported a **third** time or more           |

### Surprise-flash rule

Every incoming message normally causes a 3-second `surprised` flash, then
settles into the resolved state. **Exception:** if the previous message
arrived less than 10 seconds ago (mid-conversation), the flash is skipped.

### "Same problem" rule

The classifier extracts a 1–3 word topic per problem (e.g. `"captions"`).
The brain compares topics by **canonical-word overlap** with a small synonym
map, so all of these match each other:

- `"captions are not working"` · `"subtitles are missing"` · `"the cc is broken"`

Likewise `"audio"` ≈ `"mic"` ≈ `"sound"` ≈ `"can't hear"`, and
`"wifi"` ≈ `"internet"` ≈ `"connection"`. Edit `SYNONYMS` and `STOPWORDS` in
`emotion.py` to extend.

### Counter reset

Per-topic problem counters reset when **either** of:
- the user expresses gratitude
- the clock has been idle for 10 minutes (transition to `at_ease`)

---

## API surface (this is what the Arduino sees)

`GET /state` — current resolved state. Cheap; safe to poll.

```json
{
  "state": "anxious",
  "reaction": "oh no…",
  "version": 7,
  "meta": {
    "settles_to": "anxious",
    "active_problems": [
      { "words": ["captions"], "raw": "captions", "count": 1 }
    ],
    "seconds_since_last_message": 1.2,
    "idle_threshold": 600
  },
  "messages": [ /* recent (user message, clock reaction) pairs */ ]
}
```

State names are stable; the Arduino only needs to switch on `state`.

---

## Arduino integration (what you'll do tomorrow)

The bridge is already written. The flow is:

```
Flask /state  ──[HTTP poll, every 0.5s]──▶  bridge.py  ──[USB serial]──▶  Arduino
                                                emits one line per state change:
                                                  STATE neutral
                                                  STATE anxious
                                                  STATE embarrassed
                                                  ...
```

### Step 1 — verify the bridge prints

In one terminal:
```bash
./run.sh
```

In a second terminal:
```bash
source .venv/bin/activate
python bridge.py
```

You'll see `STATE <name>` printed in stdout every time the clock's state
changes. Use the dev panel buttons to drive transitions and watch the
bridge react.

### Step 2 — flash the reference sketch

`arduino/clock_face/clock_face.ino` listens on Serial for `STATE <name>`
lines. Open it in the Arduino IDE, pick your board, and upload. The sketch
right now just prints `[clock] -> ANXIOUS` etc. on the serial monitor —
which is enough to confirm the wire format works end-to-end.

### Step 3 — connect the bridge to the Arduino

Find the serial port (`ls /dev/tty.usbmodem*` on macOS) and run:

```bash
pip install pyserial
python bridge.py --serial /dev/tty.usbmodem1101 --baud 115200
```

The Arduino's `applyState(...)` will fire on every state change.

### Step 4 — fill in `applyState` on the Arduino

Inside `clock_face.ino`, the `switch (st)` cases are stubbed with TODO
comments. That's where you wire in:

- **OLED faces** — draw eyes/brow/mouth bitmaps for each state
- **Servos / steppers** — move the hour and minute hands to the pose for that state (the SVG face's `handsDeg` values in `static/app.js` are good starting poses)
- **Speaker** — `tone()` calls or sound clips for each state

Suggested pose mapping (mirrors the on-screen face — see `FACES` in `static/app.js`):

| state         | hour | minute | feel                    |
| ------------- | ---- | ------ | ----------------------- |
| neutral       | 10:00 | 12     | calm                   |
| at_ease       | 9:15  | 3      | leaning back            |
| joyful        | 1:55  | 11     | "arms up"               |
| surprised     | 12:00 | 12     | both hands straight up  |
| anxious       | 11:55 | 11     | tense, almost vertical  |
| embarrassed   | 11:05 | 1      | hands curled in         |
| angry         | 7:45  | 9      | crossed arms / X        |

---

## What needs your input next

You said you're working on "fine-tuning / prompt engineering the LLM categorizing part" — here's exactly where that lives and what the contract is:

1. **The prompt** is `_SYSTEM_PROMPT` in `emotion.py`. The LLM's job is just `{intent, topic}` — *not* picking the final state. Keep it narrow.
2. **The intent vocabulary** is fixed: `gratitude`, `problem`, `other`. If you want a fourth bucket, add it to `INTENTS` and handle it in `brain._resolve_target_locked()`.
3. **The topic field** must be 1–3 words and refer to *what is broken* (the noun), not how it broke. The brain matches topics by canonical-word overlap, so `"captions"` is what you want, not `"captions are gone again"`.
4. **The reactions** (the in-character lines in chat) come from `brain._REACTIONS`, **not** the LLM. You can swap to LLM-generated reactions later by extending the prompt to also return a `reaction` field and using it in `brain.on_message`. Today they're pre-written so the clock has a consistent voice and you don't pay an extra LLM round-trip per message.

Other obvious next steps, in priority order:

1. **Test the workflow today** with the dev panel + `scripts/replay.py`.
2. **Lower `IDLE_AT_EASE_SECONDS`** temporarily (e.g. to `30`) to verify the idle transition without waiting 10 minutes.
3. **Set `OPENAI_API_KEY`** if you want to test the LLM classifier vs. the heuristic. Compare results on edge cases like `"is the audio supposed to sound like that?"` (intent: problem? other?).
4. **Tomorrow:** wire `bridge.py` to the Arduino, fill in `applyState()` with OLED + servo + speaker code per state.
5. **Stretch:** add an `SSE` or websocket endpoint so the bridge gets push updates instead of polling — only worth it if 0.5s latency feels too slow on the hardware.

---

## Tunables

`brain.py`:
- `SURPRISE_FLASH_SECONDS` (default `3.0`)
- `MID_CONVERSATION_WINDOW` (default `10.0`) — skip flash inside this window
- `IDLE_AT_EASE_SECONDS` (default `600`)
- `_REACTIONS` — pools of clock lines per state

`emotion.py`:
- `SYNONYMS`, `STOPWORDS` — topic normalization for problem matching
- `_SYSTEM_PROMPT` — LLM prompt; tweak as you fine-tune
- `_PROBLEM_PATTERNS`, `_GRATITUDE_KEYWORDS` — heuristic regex
# CM_clock
