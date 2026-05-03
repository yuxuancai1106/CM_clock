/* The Clock — frontend.
 *
 *   1. Render hour ticks on the SVG clock face once.
 *   2. Continuously sweep the second hand in real time (regardless of mood).
 *   3. When state changes, morph eyes, brows, mouth, hands, cheeks, aura.
 *   4. Render messages as iMessage-style bubbles (user right, clock left).
 *   5. Show a brief typing indicator before each clock reply for delight.
 *   6. Poll /state every 2s so idle->at_ease and surprise->settled transitions
 *      surface even without new user input.
 */

(() => {
  "use strict";

  const EMOJI = {
    neutral:     "😐",
    at_ease:     "😌",
    joyful:      "😊",
    surprised:   "😮",
    anxious:     "😟",
    embarrassed: "😳",
    angry:       "😠",
  };

  // For each state, we describe how the clock's face should look.
  //   eyes     : { ry, pupilR, pupilDy }
  //   brows    : { leftD, rightD, opacity }
  //   mouth    : SVG path
  //   handsDeg : [hourDeg, minuteDeg]   -- 0 deg = pointing at 12 o'clock
  //   cheeks   : opacity (for blush)
  const FACES = {
    neutral: {
      eyes:    { ry: 9,  pupilR: 4,   pupilDy: 0 },
      brows:   { leftD: "M -42 -34 Q -30 -36 -18 -34", rightD: "M 18 -34 Q 30 -36 42 -34", opacity: .6 },
      mouth:   "M -22 22 Q 0 22 22 22",
      handsDeg: [300, 0],     // 10:00
      cheeks:  0,
    },
    at_ease: {
      eyes:    { ry: 2.5, pupilR: 2.5, pupilDy: 0 },        // sleepy half-closed
      brows:   { leftD: "M -42 -36 Q -30 -32 -18 -34", rightD: "M 18 -34 Q 30 -32 42 -36", opacity: .35 },
      mouth:   "M -20 22 Q 0 28 20 22",                      // soft smile
      handsDeg: [270, 90],    // 9:15 — relaxed
      cheeks:  0,
    },
    joyful: {
      eyes:    { ry: 4,  pupilR: 3.5, pupilDy: -1 },         // squint-smile eyes
      brows:   { leftD: "M -42 -38 Q -30 -44 -18 -38", rightD: "M 18 -38 Q 30 -44 42 -38", opacity: 1 },
      mouth:   "M -26 18 Q 0 42 26 18",                      // wide smile
      handsDeg: [30, 330],    // 1:55 — arms-up
      cheeks:  .35,
    },
    surprised: {
      eyes:    { ry: 13, pupilR: 3,   pupilDy: 0 },          // wide
      brows:   { leftD: "M -42 -42 Q -30 -48 -18 -42", rightD: "M 18 -42 Q 30 -48 42 -42", opacity: 1 },
      mouth:   "M -10 26 Q 0 38 10 26 Q 0 14 -10 26 Z",      // little 'o'
      handsDeg: [355, 5],     // 12:01 — both straight up, startled
      cheeks:  0,
    },
    anxious: {
      eyes:    { ry: 11, pupilR: 4,   pupilDy: 0 },          // wide & alert
      brows:   { leftD: "M -42 -30 Q -30 -40 -18 -36", rightD: "M 18 -36 Q 30 -40 42 -30", opacity: 1 },  // worry tilt
      mouth:   "M -22 24 Q -8 18 0 24 Q 8 30 22 22",          // wavy
      handsDeg: [355, 175],    // 11:55 / pointing — tense
      cheeks:  0,
    },
    embarrassed: {
      eyes:    { ry: 5,  pupilR: 3,   pupilDy: 1 },          // half-closed, looking down
      brows:   { leftD: "M -42 -32 Q -30 -38 -18 -34", rightD: "M 18 -34 Q 30 -38 42 -32", opacity: .9 },
      mouth:   "M -16 24 Q -4 20 4 24 Q 12 28 18 22",        // small awkward squiggle
      handsDeg: [330, 30],    // 11:05 — folded
      cheeks:  .85,           // BLUSH
    },
    angry: {
      eyes:    { ry: 4,  pupilR: 4.5, pupilDy: 1 },          // narrowed
      brows:   { leftD: "M -42 -32 L -18 -40", rightD: "M 18 -40 L 42 -32", opacity: 1 },                 // sharp /\
      mouth:   "M -22 28 Q 0 18 22 28",                      // hard frown
      handsDeg: [225, 135],   // 7:45 — slashed X
      cheeks:  0,
    },
  };

  // --- SVG element refs -----------------------------------------------------

  const $body        = document.body;
  const $clock       = document.querySelector(".clock");
  const $ticks       = $clock.querySelector(".ticks");

  const $eyeWhiteL   = $clock.querySelector(".eye-left .eye-white");
  const $eyeWhiteR   = $clock.querySelector(".eye-right .eye-white");
  const $pupilL      = $clock.querySelector(".eye-left .pupil");
  const $pupilR      = $clock.querySelector(".eye-right .pupil");
  const $browL       = $clock.querySelector(".brow-left");
  const $browR       = $clock.querySelector(".brow-right");
  const $mouth       = $clock.querySelector(".mouth");
  const $cheekL      = $clock.querySelector(".cheek-left");
  const $cheekR      = $clock.querySelector(".cheek-right");

  const $handHour    = $clock.querySelector(".hand-hour");
  const $handMinute  = $clock.querySelector(".hand-minute");
  const $handSecond  = $clock.querySelector(".hand-second");

  const $statusEmoji = document.querySelector(".status-emoji");
  const $statusWord  = document.querySelector(".status-word");

  const $messages    = document.querySelector(".messages");
  const $typingRow   = document.querySelector(".typing-row");
  const $form        = document.querySelector(".composer");
  const $textIn      = $form.querySelector(".message-input");
  const $sendBtn     = $form.querySelector(".send-btn");

  // Dev panel
  const $devPanel    = document.querySelector(".dev-panel");
  const $devToggle   = $devPanel.querySelector(".dev-toggle");
  const $devEmoji    = $devPanel.querySelector(".dev-big-emoji");
  const $devName     = $devPanel.querySelector(".dev-state-name");
  const $devSettles  = $devPanel.querySelector(".dev-settles");
  const $devTimeline = $devPanel.querySelector(".dev-timeline");
  const $devLastMsg  = $devPanel.querySelector(".dev-last-msg");
  const $devLastState = $devPanel.querySelector(".dev-last-state");
  const $devLastTop  = $devPanel.querySelector(".dev-last-topic");
  const $devLastFlash = $devPanel.querySelector(".dev-last-flash");
  const $devSince    = $devPanel.querySelector(".dev-since");
  const $devIdle     = $devPanel.querySelector(".dev-idle");
  const $devVersion  = $devPanel.querySelector(".dev-version");
  const $devJson     = $devPanel.querySelector(".dev-json");
  const $devShortcuts = $devPanel.querySelector(".dev-shortcuts");

  const TEST_SCRIPTS = {
    "problem-once":   "the captions are not working",
    "problem-twice":  "subtitles are still missing",
    "problem-thrice": "still no captions please",
    "caps-rage":      "FIX THE CAPTIONS NOW",
    "frustrated":     "ugh this is so frustrating, are you kidding me",
    "thanks":         "thank you so much, this is wonderful",
    "hello":          "hello clock, how are you today",
  };

  // --- Render clock ticks (once) -------------------------------------------

  for (let i = 0; i < 12; i++) {
    const angle = (i * 30) * Math.PI / 180;
    const r1 = i % 3 === 0 ? 70 : 76;
    const r2 = 82;
    const x1 = Math.sin(angle) * r1;
    const y1 = -Math.cos(angle) * r1;
    const x2 = Math.sin(angle) * r2;
    const y2 = -Math.cos(angle) * r2;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", x1.toFixed(2));
    line.setAttribute("y1", y1.toFixed(2));
    line.setAttribute("x2", x2.toFixed(2));
    line.setAttribute("y2", y2.toFixed(2));
    if (i % 3 === 0) line.classList.add("major");
    $ticks.appendChild(line);
  }

  // --- Apply state to the face ---------------------------------------------

  function applyState(state) {
    const face = FACES[state] || FACES.neutral;

    $body.dataset.state = state;

    $eyeWhiteL.setAttribute("ry", face.eyes.ry);
    $eyeWhiteR.setAttribute("ry", face.eyes.ry);
    $pupilL.setAttribute("r", face.eyes.pupilR);
    $pupilR.setAttribute("r", face.eyes.pupilR);
    $pupilL.setAttribute("cy", -18 + face.eyes.pupilDy);
    $pupilR.setAttribute("cy", -18 + face.eyes.pupilDy);

    $browL.setAttribute("d", face.brows.leftD);
    $browR.setAttribute("d", face.brows.rightD);
    $browL.style.opacity = face.brows.opacity;
    $browR.style.opacity = face.brows.opacity;

    $mouth.setAttribute("d", face.mouth);

    $cheekL.style.opacity = face.cheeks;
    $cheekR.style.opacity = face.cheeks;

    $handHour.style.transform   = `rotate(${face.handsDeg[0]}deg)`;
    $handMinute.style.transform = `rotate(${face.handsDeg[1]}deg)`;

    $statusEmoji.textContent = EMOJI[state] || "😐";
    $statusWord.textContent  = state.replace("_", " ");
  }

  // --- Continuously sweep the second hand ----------------------------------

  function tickSecondHand() {
    const now = new Date();
    const seconds = now.getSeconds() + now.getMilliseconds() / 1000;
    $handSecond.style.transform = `rotate(${seconds * 6}deg)`;
    requestAnimationFrame(tickSecondHand);
  }
  requestAnimationFrame(tickSecondHand);

  // --- Render messages -----------------------------------------------------
  //
  // Server returns a flat list of message records. Each record is the user's
  // message; the clock's reaction is `record.reaction`. We render them as a
  // pair of bubbles: user (right) then clock (left).

  // Two parallel sets so user-bubble and clock-bubble dedupe independently
  // (one logical message = one user bubble + one clock bubble).
  const renderedUserIds  = new Set();
  const renderedClockIds = new Set();
  let lastBubbleAuthor = null;

  function makeId() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return "msg-" + Math.random().toString(36).slice(2) + "-" + Date.now().toString(36);
  }

  function appendUserBubble(text, ts) {
    maybeAppendTimestamp(ts);
    const row = document.createElement("div");
    row.className = "bubble-row from-user" + (lastBubbleAuthor === "user" ? " tight" : "");
    const bub = document.createElement("div");
    bub.className = "bubble";
    bub.textContent = text;
    row.appendChild(bub);
    $messages.appendChild(row);
    lastBubbleAuthor = "user";
  }

  function appendClockBubble(text, settledTo, topic) {
    const row = document.createElement("div");
    row.className = "bubble-row from-clock" + (lastBubbleAuthor === "clock" ? " tight" : "");
    const bub = document.createElement("div");
    bub.className = "bubble";
    bub.textContent = text;
    row.appendChild(bub);

    if (settledTo) {
      const tag = document.createElement("div");
      tag.className = "tag";
      const parts = [`${EMOJI[settledTo] || ""} ${settledTo.replace("_", " ")}`];
      if (topic) parts.push(`topic: ${topic}`);
      tag.textContent = parts.join("  ·  ");
      row.appendChild(tag);
    }

    $messages.appendChild(row);
    lastBubbleAuthor = "clock";
  }

  function maybeAppendTimestamp(ts) {
    // Insert a centered timestamp if last one was long ago (or this is first).
    const lastStamp = $messages.querySelector(".timestamp:last-of-type");
    const now = ts * 1000;
    if (!lastStamp || now - Number(lastStamp.dataset.ts) > 5 * 60 * 1000) {
      const stamp = document.createElement("div");
      stamp.className = "timestamp";
      stamp.dataset.ts = String(now);
      stamp.textContent = formatStamp(now);
      $messages.appendChild(stamp);
      lastBubbleAuthor = null;
    }
  }

  function formatStamp(ms) {
    const d = new Date(ms);
    const opts = { weekday: "short", hour: "2-digit", minute: "2-digit" };
    return d.toLocaleString([], opts);
  }

  function renderNewMessages(messages) {
    for (const m of messages) {
      if (!m.id) continue;        // server always provides id now
      if (!renderedUserIds.has(m.id)) {
        renderedUserIds.add(m.id);
        appendUserBubble(m.text, m.ts);
      }
      if (m.reaction && !renderedClockIds.has(m.id)) {
        renderedClockIds.add(m.id);
        appendClockBubble(m.reaction, m.state || m.settles_to, m.topic);
      }
    }
    $messages.scrollTop = $messages.scrollHeight;
  }

  function showTyping(on) {
    $typingRow.hidden = !on;
    if (on) $messages.scrollTop = $messages.scrollHeight;
  }

  // --- Networking ----------------------------------------------------------

  let lastVersion = -1;

  async function fetchState() {
    try {
      const resp = await fetch("/state");
      if (!resp.ok) return;
      const state = await resp.json();
      handleState(state, /*fromUserSubmit=*/false);
    } catch (e) {
      // network blip — try again next poll
    }
  }

  function handleState(payload, fromUserSubmit) {
    if (payload.version !== lastVersion) {
      lastVersion = payload.version;
      applyState(payload.state);
    }
    if (!fromUserSubmit) {
      renderNewMessages(payload.messages || []);
    }
    updateDevPanel(payload);
  }

  // ----------------------------------------------------------------- dev ---

  function updateDevPanel(payload) {
    const state = payload.state || "neutral";
    $devEmoji.textContent = EMOJI[state] || "😐";
    $devName.textContent  = state.replace("_", " ");
    $devSettles.textContent = (payload.meta && payload.meta.settles_to) || "—";

    // Recent timeline: last 6 messages with state pills (newest first).
    const history = (payload.meta && payload.meta.history) || [];
    $devTimeline.innerHTML = "";
    if (history.length === 0) {
      const li = document.createElement("li");
      li.className = "dev-empty";
      li.textContent = "no messages yet";
      $devTimeline.appendChild(li);
    } else {
      const recent = history.slice(-6).reverse();
      for (const h of recent) {
        const li = document.createElement("li");
        li.className = `dev-timeline-item state-${h.state}`;
        const pill = document.createElement("span");
        pill.className = "pill";
        pill.textContent = `${EMOJI[h.state] || ""} ${h.state.replace("_", " ")}`;
        const text = document.createElement("span");
        text.className = "msg";
        text.textContent = h.text;
        li.append(pill, text);
        $devTimeline.appendChild(li);
      }
    }

    const last = history[history.length - 1];
    if (last) {
      $devLastMsg.textContent = last.text;
      $devLastState.textContent = last.state;
      $devLastTop.textContent = last.topic || "—";
      $devLastFlash.textContent = last.flashed_surprise ? "yes" : "no";
    }

    const since = payload.meta && payload.meta.seconds_since_last_message;
    $devSince.textContent = since == null ? "—" : `${since}s ago`;
    const idle = payload.meta && payload.meta.idle_threshold;
    if (idle != null) $devIdle.textContent = `${idle}s`;
    $devVersion.textContent = String(payload.version);

    $devJson.textContent = JSON.stringify(payload, null, 2);
  }

  $devToggle.addEventListener("click", () => {
    const collapsed = $devPanel.dataset.collapsed === "true";
    $devPanel.dataset.collapsed = collapsed ? "false" : "true";
    $devToggle.textContent = collapsed ? "−" : "+";
  });

  $devShortcuts.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-test]");
    if (!btn) return;
    const text = TEST_SCRIPTS[btn.dataset.test];
    if (!text) return;
    sendMessage(text);
  });

  async function sendMessage(text) {
    $sendBtn.disabled = true;

    // Generate a stable client-side id, mark the user bubble as already
    // rendered for this id, and paint it optimistically. The server will use
    // the same id for the history entry so the polling loop won't duplicate.
    const clientMsgId = makeId();
    renderedUserIds.add(clientMsgId);
    appendUserBubble(text, Date.now() / 1000);
    $messages.scrollTop = $messages.scrollHeight;

    showTyping(true);

    try {
      const resp = await fetch("/message", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, client_msg_id: clientMsgId }),
      });
      if (!resp.ok) {
        showTyping(false);
        return;
      }
      const data = await resp.json();

      // Hold the typing indicator for at least 600ms — feels more alive.
      setTimeout(() => {
        showTyping(false);
        // Mark the clock bubble for this id as rendered before we paint it.
        renderedClockIds.add(data.message.id);
        appendClockBubble(
          data.message.reaction,
          data.message.settles_to,
          data.message.topic,
        );
        applyState(data.state.state);
        lastVersion = data.state.version;
        $messages.scrollTop = $messages.scrollHeight;
      }, 600);
    } finally {
      $sendBtn.disabled = false;
      $textIn.focus();
    }
  }

  $form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = $textIn.value.trim();
    if (!text) return;
    $textIn.value = "";
    sendMessage(text);
  });

  // Initial paint + polling for time-driven transitions (surprise->settled, idle->at_ease).
  applyState("neutral");
  fetchState();
  setInterval(fetchState, 2000);
})();
