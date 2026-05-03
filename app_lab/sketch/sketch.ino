/**
 * Flask clock → Modulino matrix (Arduino App Lab / companion Python)
 *
 * - Polls NOTHING here by default — Python `main.py` calls Bridge API or you
 *   send ASCII lines over USB Serial during bring-up:
 *       joyful
 *       STATE joyful
 *
 * Matches Flask /state strings exactly:
 * neutral, at_ease, joyful, surprised, anxious, embarrassed, angry
 */
#include <Arduino.h>
#include "emotion.h"

#ifndef BRIDGE_POLL_MS
#define BRIDGE_POLL_MS 5
#endif

static uint8_t  s_bankIdx   = 0;
static uint8_t  s_frameIdx  = 0;
static uint32_t s_nextTicks = 0;

static void redrawCurrentFrame(void) {
  const EmotionBankEntry *b = bankEntry(s_bankIdx);
  if (b->frame_count == 0) {
    return;
  }
  s_frameIdx = (uint8_t)(s_frameIdx % b->frame_count);
  hardwareDrawMatrix(b->frames[s_frameIdx]);
}

static void bumpAnimationSchedule(void) {
  const EmotionBankEntry *b = bankEntry(s_bankIdx);
  if (b->frame_count == 0) {
    return;
  }
  const EmotionFrame &f = b->frames[s_frameIdx];
  s_nextTicks = millis() + f.duration_ms;
}

void onStateChanged(const String &state) {
  uint8_t idx = emotionIndexForState(state);
  if (idx == 255) {
    idx = 0;  /* unknown → neutral */
  }

  Serial.print(F("[Sketch] >>> STATE CHANGED: "));
  Serial.print(state);
  Serial.print(F(" ("));
  Serial.print(idx);
  Serial.println(F(")"));

  s_bankIdx  = idx;
  s_frameIdx = 0;
  redrawCurrentFrame();
  bumpAnimationSchedule();
}

/* --------------------------------------------------------------------------
 * Arduino App Lab: wire Bridge.call("set_state", "<name>") to this handler.
 * Exact API differs by IDE version — search docs for Bridge / RPC / Lab.
 *
 * Fallback below: SERIAL lines during bench test.
 * --------------------------------------------------------------------------
 */
#if defined(APPLAB_BRIDGE_AVAILABLE)
void bridge_set_state(const String &payload) {
  onStateChanged(payload);
}
#endif

static void consumeSerial_lines(void) {
  static String buf;
  while (Serial.available()) {
    char c = static_cast<char>(Serial.read());
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      String line = buf;
      buf       = "";
      line.trim();
      if (line.length() == 0) {
        continue;
      }
      if (line.startsWith(F("STATE "))) {
        line = line.substring(6);
      }
      line.trim();
      onStateChanged(line);
      return;
    }
    if (buf.length() < 64) {
      buf += c;
    }
  }
}

static void tickAnimation(void) {
  uint32_t now = millis();
  if ((int32_t)(now - s_nextTicks) >= 0) {
    const EmotionBankEntry *b = bankEntry(s_bankIdx);
    if (b->frame_count > 1U) {
      s_frameIdx = (uint8_t)((s_frameIdx + 1U) % b->frame_count);
      redrawCurrentFrame();
    }
    bumpAnimationSchedule();
  }
}

void setup(void) {
  Serial.begin(115200);
#if defined(USBCON)
  unsigned long boot = millis();
  while (!Serial && (millis() - boot < 3000UL)) {
    delay(25);
  }
#endif

  Serial.println(F("[Sketch] Modulino clock bridge — waiting states…"));
  onStateChanged("neutral");
}

void loop(void) {
  consumeSerial_lines();
#if defined(APPLAB_BRIDGE_AVAILABLE)
  /* Bridge.poll(); Bridge.parse(); … */
#endif
  tickAnimation();
  delay(BRIDGE_POLL_MS);
}
