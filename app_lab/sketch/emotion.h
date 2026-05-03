#pragma once
/**
 * Modulino-class LED matrix — placeholder bitmaps for each Flask `state`.
 *
 * Layout per frame:
 *   r0,r1,r2,r3 — four horizontal scan rows (lower 16 bits = 16 columns; tweak for your HW)
 *   duration_ms — hold time before next frame (loop)
 *
 * These are placeholders: replace hex values once you see them on real hardware.
 */
#include <Arduino.h>

typedef struct __attribute__((packed)) {
  uint32_t r0, r1, r2, r3;
  uint32_t duration_ms;
} EmotionFrame;

#define EF(a, b, c, d, ms) \
  { (uint32_t)(a), (uint32_t)(b), (uint32_t)(c), (uint32_t)(d), (uint32_t)(ms) }

static const EmotionFrame SEQ_NEUTRAL[] = {
    EF(0x1824, 0x8142, 0xFFC0, 0x03C0, 500),
    EF(0x1824, 0x8142, 0xFFC0, 0x0380, 500),
};

static const EmotionFrame SEQ_AT_EASE[] = {
    EF(0x1008, 0x63C7, 0xFFC0, 0x0780, 650),
    EF(0x1008, 0x6387, 0xFF80, 0x0700, 650),
};

static const EmotionFrame SEQ_JOYFUL[] = {
    EF(0x1824, 0x8142, 0xFFC0, 0x07E0, 220),
    EF(0x1824, 0x0042, 0xFFC0, 0x07E0, 220),
    EF(0x1824, 0x8142, 0xFFC0, 0x07E0, 220),
};

static const EmotionFrame SEQ_SURPRISED[] = {
    EF(0x3C3C, 0x8142, 0xFFC0, 0x0780, 160),
    EF(0x3C3C, 0xFFFF, 0xFFC0, 0x0780, 160),
};

static const EmotionFrame SEQ_ANXIOUS[] = {
    EF(0x1818, 0x4244, 0xE7C0, 0x03C0, 350),
    EF(0x300C, 0x4244, 0xE780, 0x0380, 350),
};

static const EmotionFrame SEQ_EMBARRASSED[] = {
    EF(0x2400, 0x8142, 0xFFC0, 0x0360, 400),
    EF(0x4200, 0x8142, 0xFFC0, 0x0360, 400),
};

static const EmotionFrame SEQ_ANGRY[] = {
    EF(0x6600, 0x9942, 0xFFC0, 0x0180, 180),
    EF(0xCC00, 0x9242, 0xFFC0, 0x0240, 180),
    EF(0x6600, 0x9942, 0xFFC0, 0x0180, 180),
};

#undef EF

typedef struct {
  const char *name;
  const EmotionFrame *frames;
  uint8_t frame_count;
} EmotionBankEntry;

inline uint8_t countFrames(const EmotionFrame *a, size_t bytes) {
  return (uint8_t)(bytes / sizeof(EmotionFrame));
}

// Order must match Flask /state strings exactly:
static const EmotionBankEntry EMOTION_BANK[] = {
    {"neutral", SEQ_NEUTRAL, countFrames(SEQ_NEUTRAL, sizeof(SEQ_NEUTRAL))},
    {"at_ease", SEQ_AT_EASE, countFrames(SEQ_AT_EASE, sizeof(SEQ_AT_EASE))},
    {"joyful", SEQ_JOYFUL, countFrames(SEQ_JOYFUL, sizeof(SEQ_JOYFUL))},
    {"surprised", SEQ_SURPRISED, countFrames(SEQ_SURPRISED, sizeof(SEQ_SURPRISED))},
    {"anxious", SEQ_ANXIOUS, countFrames(SEQ_ANXIOUS, sizeof(SEQ_ANXIOUS))},
    {"embarrassed", SEQ_EMBARRASSED, countFrames(SEQ_EMBARRASSED, sizeof(SEQ_EMBARRASSED))},
    {"angry", SEQ_ANGRY, countFrames(SEQ_ANGRY, sizeof(SEQ_ANGRY))},
};

static const uint8_t EMOTION_BANK_LEN =
    (uint8_t)(sizeof(EMOTION_BANK) / sizeof(EMOTION_BANK[0]));

/** Returns index [0 .. EMOTION_BANK_LEN-1] or 255 if unknown */
inline uint8_t emotionIndexForState(const String &state) {
  for (uint8_t i = 0; i < EMOTION_BANK_LEN; i++) {
    if (state.equals(EMOTION_BANK[i].name)) {
      return i;
    }
  }
  return 255;
}

inline const EmotionBankEntry *bankEntry(uint8_t idx) {
  if (idx >= EMOTION_BANK_LEN) {
    return &EMOTION_BANK[0];  // fallback neutral
  }
  return &EMOTION_BANK[idx];
}

/** Push bitmap to hardware HERE (Modulino / LED driver) */
inline void hardwareDrawMatrix(const EmotionFrame &f) {
  (void)f;
#if 0  // Plug in Modulino API
  // Matrix.begin(); … draw f.r0..r3
#endif
}
