// clock_face.ino — minimal sketch that listens for STATE commands from bridge.py
//
// Wiring assumptions (adjust freely):
//   - 2x SSD1306 OLED on I2C (or one with a chip-select multiplexer)
//   - 2x small servos on pins 9, 10 for hour + minute hands
//   - 1x piezo speaker on pin 8
//
// Protocol (one ASCII line per state change, newline-terminated):
//   STATE neutral
//   STATE at_ease
//   STATE joyful
//   STATE surprised
//   STATE anxious
//   STATE embarrassed
//   STATE angry
//
// On boot, the sketch sits in `neutral` until the first command arrives.

#include <Arduino.h>
// #include <Servo.h>
// #include <Wire.h>
// #include <Adafruit_SSD1306.h>

enum ClockState {
  S_NEUTRAL, S_AT_EASE, S_JOYFUL, S_SURPRISED,
  S_ANXIOUS, S_EMBARRASSED, S_ANGRY, S_UNKNOWN
};

ClockState parseState(const String& s) {
  if (s == "neutral")     return S_NEUTRAL;
  if (s == "at_ease")     return S_AT_EASE;
  if (s == "joyful")      return S_JOYFUL;
  if (s == "surprised")   return S_SURPRISED;
  if (s == "anxious")     return S_ANXIOUS;
  if (s == "embarrassed") return S_EMBARRASSED;
  if (s == "angry")       return S_ANGRY;
  return S_UNKNOWN;
}

void applyState(ClockState st) {
  switch (st) {
    case S_NEUTRAL:
      // TODO: draw flat eyes + flat mouth on OLEDs; servos to 10:10; speaker silent
      Serial.println("[clock] -> NEUTRAL");
      break;
    case S_AT_EASE:
      // TODO: draw half-closed eyes + soft smile; servos to 9:15; gentle "tick" tone
      Serial.println("[clock] -> AT_EASE");
      break;
    case S_JOYFUL:
      // TODO: draw smile-eyes + big smile; servos to 1:55; happy chirp
      Serial.println("[clock] -> JOYFUL");
      break;
    case S_SURPRISED:
      // TODO: draw wide eyes + 'o' mouth; servos to 12:00; quick "ding!"
      Serial.println("[clock] -> SURPRISED");
      break;
    case S_ANXIOUS:
      // TODO: draw worried brows + wavy mouth; servos to 11:55 tense; soft buzz
      Serial.println("[clock] -> ANXIOUS");
      break;
    case S_EMBARRASSED:
      // TODO: draw blushing face (pink fill if RGB); servos folded; quiet sigh
      Serial.println("[clock] -> EMBARRASSED");
      break;
    case S_ANGRY:
      // TODO: draw angry brows + frown; servos to 7:45 (crossed); ticking faster + buzz
      Serial.println("[clock] -> ANGRY");
      break;
    default:
      Serial.print("[clock] unknown state\n");
  }
}

void setup() {
  Serial.begin(115200);
  // hourServo.attach(9); minuteServo.attach(10);
  // display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  applyState(S_NEUTRAL);
}

String inbuf;

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (inbuf.length() > 0) {
        // Expect: "STATE <name>"
        int sp = inbuf.indexOf(' ');
        if (sp > 0 && inbuf.substring(0, sp) == "STATE") {
          String name = inbuf.substring(sp + 1);
          name.trim();
          applyState(parseState(name));
        }
        inbuf = "";
      }
    } else {
      inbuf += c;
      if (inbuf.length() > 64) inbuf = "";  // protect against runaway input
    }
  }
}
