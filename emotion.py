"""Message classification for the Clock.

The LLM (or heuristic fallback) reads a single user message PLUS a small slice
of recent conversation history, and returns one of five emotional states:

    neutral | joyful | anxious | embarrassed | angry

(The two remaining states — `surprised` and `at_ease` — are time-driven and
owned by the ClockBrain; the LLM never picks them.)

Tone matters:
  - ALL-CAPS / multiple !!! / harsh words   -> angry
  - thanks / praise                         -> joyful
  - new problem reported calmly             -> anxious
  - same problem reported again (history)   -> embarrassed
  - same problem a 3rd+ time / yelling      -> angry

Both code paths return the same shape:

    Classification(state="anxious", topic="captions")
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

# States the LLM is allowed to pick from.
LLM_STATES: tuple[str, ...] = ("neutral", "joyful", "anxious", "embarrassed", "angry")


@dataclass(frozen=True)
class Classification:
    state: str
    topic: str = ""

    def to_dict(self) -> dict:
        return {"state": self.state, "topic": self.topic}


# ---------------------------------------------------------------------------
# Heuristic classifier (offline fallback)
# ---------------------------------------------------------------------------

_GRATITUDE_KEYWORDS = (
    "thank", "thanks", "thx", "ty", "appreciate", "appreciated", "grateful",
    "love it", "love this", "well done", "great job", "amazing job", "good job",
    "nice work", "you're the best", "youre the best",
)

_ANGRY_WORDS = (
    "wtf", "fix it", "fix this", "are you kidding", "ridiculous", "useless",
    "garbage", "terrible", "fucking", "stupid", "hate this",
)

_PROBLEM_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"\bnot working\b", r"\bisn'?t working\b", r"\bdoesn'?t work\b",
    r"\bbroken\b", r"\bbreaks?\b",
    r"\b(?:can'?t|cannot) (?:hear|see|read|find|use|access|connect|join|open)\b",
    r"\bwon'?t (?:load|start|work|play|open|connect)\b",
    r"\bno (?:audio|sound|video|captions?|subtitles?|wifi|internet|signal|service|connection)\b",
    r"\b(?:issue|issues|problem|problems|error|errors|bug|bugs|glitch)\b",
    r"\bmissing\b", r"\b(?:muted|on mute)\b",
    r"\bplease fix\b", r"\bneeds? fixing\b", r"\bno signal\b",
    r"\b(?:still|again).*(?:not|no|broken|missing|gone|down|dead|out)\b",
    r"\b(?:is|are|was|were|got|keeps?)\s+(?:gone|dead|down|out|stuck|cut\s+off|cutting\s+out)\b",
    r"\bstopped (?:working|loading|playing|responding)\b",
    r"\bnot (?:anymore|loading|showing|playing)\b",
    r"\b(?:gone|missing) again\b",
    r"\bcrash(?:ed|ing)?\b", r"\bfrozen\b", r"\blagging\b",
))


def _is_yelling(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 4:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio >= 0.7:
            return True
    if text.count("!") >= 3:
        return True
    return False


def _extract_topic(message: str) -> str:
    """Pull the first 1-3 noteworthy nouns from the message."""
    stop = {
        "the", "a", "an", "is", "are", "and", "or", "but", "to", "of", "in",
        "on", "at", "for", "with", "i", "we", "my", "our", "this", "that",
        "it", "be", "been", "do", "does", "did", "can", "cannot", "cant",
        "won", "wont", "im", "you", "your", "not", "no", "still", "again",
        "really", "very", "just", "work", "working", "broken", "fix", "issue",
        "problem", "missing", "wrong", "bad", "keep", "keeps", "going", "gone",
        "got", "stop", "stopped", "dead", "down", "out", "stuck",
    }
    words = re.findall(r"[A-Za-z]+", message)
    chosen = [w for w in words if w.lower() not in stop and len(w) > 2]
    return " ".join(chosen[:3])


def _looked_like_repeat(message: str, history: list[dict]) -> bool:
    """Naive repeat detector for the heuristic path: is this user message
    talking about a topic we've seen recently?"""
    if not history:
        return False
    new_topic = _extract_topic(message).lower()
    if not new_topic:
        return False
    new_words = set(new_topic.split())
    for h in history[-6:]:
        prev = (h.get("topic") or "").lower()
        if prev:
            if new_words & set(prev.split()):
                return True
    return False


def _heuristic_classify(message: str, history: list[dict] | None = None) -> Classification:
    text = message.strip()
    if not text:
        return Classification(state="neutral")
    history = history or []
    lower = text.lower()

    if _is_yelling(text) or any(w in lower for w in _ANGRY_WORDS):
        return Classification(state="angry", topic=_extract_topic(text))

    if any(kw in lower for kw in _GRATITUDE_KEYWORDS):
        return Classification(state="joyful")

    if any(p.search(text) for p in _PROBLEM_PATTERNS):
        topic = _extract_topic(text)
        # Count how many prior problem messages share a topic word.
        repeats = sum(
            1 for h in history
            if h.get("state") in ("anxious", "embarrassed", "angry")
            and set(_extract_topic(h.get("text", "")).lower().split())
                & set(topic.lower().split())
        )
        if repeats >= 2:
            return Classification(state="angry", topic=topic)
        if repeats == 1:
            return Classification(state="embarrassed", topic=topic)
        return Classification(state="anxious", topic=topic)

    return Classification(state="neutral")


# ---------------------------------------------------------------------------
# LLM classifier
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are the inner monologue of a sentient antique clock listening to a room of people during a live event.

For each new user message, decide the clock's emotional reaction. Output exactly ONE of these 5 states:

  - "neutral"     : default. Greetings, small talk, casual statements, neutral updates.
  - "joyful"      : the speaker expresses gratitude, thanks, praise, or delight.
  - "anxious"     : the speaker reports a NEW problem or concern for the FIRST time, calmly.
  - "embarrassed" : the same concern from earlier in the conversation is being raised AGAIN (use the history).
  - "angry"       : the speaker is yelling (ALL CAPS, multiple !!!, harsh language, swearing, "fix it", "ridiculous", etc.) OR the same problem is reported a 3rd+ time.

TONE OVERRIDES TOPIC. If the speaker is clearly yelling/furious, the state is "angry" even if the underlying issue is new. CAPITALIZATION and punctuation are strong signals.

Also extract `topic`: a short noun phrase (1-3 words) describing what is broken/missing,
ONLY if the message is about a problem (anxious/embarrassed/angry-with-topic). Use the
broken thing itself ("captions", "audio", "wifi"), not adjectives. Empty string otherwise.

Examples:

USER: "hello clock"
→ {"state":"neutral","topic":""}

USER: "thank you so much, this is wonderful!"
→ {"state":"joyful","topic":""}

USER: "the captions aren't working"
(no prior problems)
→ {"state":"anxious","topic":"captions"}

USER: "still no captions, please fix it"
(history shows a captions complaint earlier)
→ {"state":"embarrassed","topic":"captions"}

USER: "FIX THE CAPTIONS NOW"
→ {"state":"angry","topic":"captions"}

USER: "WHY ISN'T THIS WORKING?!?!"
→ {"state":"angry","topic":""}

USER: "ugh this is so frustrating, are you kidding me"
→ {"state":"angry","topic":""}

USER: "i can't hear anything"
(no prior problems)
→ {"state":"anxious","topic":"audio"}

USER: "subtitles are missing"
(history shows captions complaint earlier — same topic)
→ {"state":"embarrassed","topic":"captions"}

USER: "how's the weather?"
→ {"state":"neutral","topic":""}

USER: "AMAZING WORK!!!"
(positive yelling — joyful, not angry)
→ {"state":"joyful","topic":""}

Return ONLY the raw JSON object. No markdown code fences. No commentary."""


def _format_history(history: list[dict]) -> str:
    if not history:
        return "(no prior messages)"
    lines = []
    for h in history[-8:]:
        text = (h.get("text") or "").replace("\n", " ").strip()
        if not text:
            continue
        state = h.get("state") or "neutral"
        topic = h.get("topic") or ""
        topic_part = f" [topic: {topic}]" if topic else ""
        lines.append(f'- "{text}" → {state}{topic_part}')
    return "\n".join(lines) if lines else "(no prior messages)"


def _build_user_prompt(message: str, history: list[dict]) -> str:
    return (
        "Conversation so far (oldest first):\n"
        f"{_format_history(history)}\n\n"
        f'Latest message: "{message}"'
    )


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def _coerce(parsed: dict | None) -> Classification | None:
    if not isinstance(parsed, dict):
        return None
    state = str(parsed.get("state", "neutral")).lower().strip()
    if state not in LLM_STATES:
        state = "neutral"
    topic = str(parsed.get("topic", "")).strip()
    if state in ("neutral", "joyful"):
        topic = ""
    return Classification(state=state, topic=topic)


def _http_post(url: str, headers: dict[str, str], body: dict) -> dict | None:
    from urllib import error as urlerror
    from urllib import request as urlrequest
    req = urlrequest.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers=headers, method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urlerror.URLError, TimeoutError, json.JSONDecodeError):
        return None


def _anthropic_classify(message: str, history: list[dict]) -> Classification | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
    body = _http_post(
        "https://api.anthropic.com/v1/messages",
        {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        {
            "model": model,
            "max_tokens": 200,
            "temperature": 0.2,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": _build_user_prompt(message, history)}],
        },
    )
    if body is None:
        return None
    try:
        text = body["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return None
    return _coerce(_extract_json(text))


def _openai_classify(message: str, history: list[dict]) -> Classification | None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    body = _http_post(
        "https://api.openai.com/v1/chat/completions",
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        {
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(message, history)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        },
    )
    if body is None:
        return None
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    return _coerce(_extract_json(content))


def llm_provider() -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "heuristic"


def classify(message: str, history: list[dict] | None = None) -> Classification:
    """Classify a message. Tries Anthropic, then OpenAI, then the heuristic.

    `history` is an optional list of recent message records. Each record can
    have keys: text, state, topic. Used to detect repeated problems.
    """
    history = history or []
    provider = llm_provider()
    if provider == "anthropic":
        result = _anthropic_classify(message, history)
        if result is not None:
            return result
    elif provider == "openai":
        result = _openai_classify(message, history)
        if result is not None:
            return result
    return _heuristic_classify(message, history)
