/*
 * Clock state over Wi-Fi — ESP32 (replaces laptop USB + bridge.py)
 *
 * Your webpage talks to Flask (on your laptop, ngrok, or Render).
 * bridge.py polls GET /state and sends "STATE xxx" over USB cable.
 *
 * If you CANNOT plug the Arduino/laptop together: use Wi-Fi —
 * ESP32 joins the SAME Wi‑Fi as guests (e.g. school Wi‑Fi) and polls /state itself.
 *
 * Plain Arduino UNO cannot do HTTPS easily; ESP32 CAN.
 *
 * 1. Edit WIFI_SSID, WIFI_PASSWORD, STATE_URL below.
 * 2. Board: "ESP32 Dev Module" or your exact board in Arduino IDE.
 * 3. Upload, open Serial Monitor @ 115200.
 * 4. Change emotion on your public URL — Serial should print NEUTRAL, JOYFUL, …
 */

#include <Arduino.h>

#if !defined(ARDUINO_ARCH_ESP32)
#error "This sketch targets ESP32. For UNO-only + no cable see comments at bottom."
#else
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClient.h>
#include <WiFiClientSecure.h>
#endif

// ---- EDIT THESE ------------------------------------------------------------
static const char *WIFI_SSID     = "YOUR_WIFI_NAME";
static const char *WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Exact URL Flask serves for GET /state (include trailing /state path)
static const char *STATE_URL =
    "https://YOUR_TUNNEL.ngrok-free.app/state";

static const char *SKIP_WARN_NAME  = "ngrok-skip-browser-warning";
static const char *SKIP_WARN_VALUE = "true";

static const unsigned POLL_MS    = 500;
static const unsigned SERIAL_BAUD = 115200;
// ----------------------------------------------------------------------------

enum ClockState {
  ST_UNKNOWN = 0,
  ST_NEUTRAL,
  ST_AT_EASE,
  ST_JOYFUL,
  ST_SURPRISED,
  ST_ANXIOUS,
  ST_EMBARRASSED,
  ST_ANGRY,
};

static String g_lastRawState;

ClockState parseStateEnum(const String &s) {
  if (s == "neutral")     return ST_NEUTRAL;
  if (s == "at_ease")     return ST_AT_EASE;
  if (s == "joyful")      return ST_JOYFUL;
  if (s == "surprised")   return ST_SURPRISED;
  if (s == "anxious")     return ST_ANXIOUS;
  if (s == "embarrassed") return ST_EMBARRASSED;
  if (s == "angry")       return ST_ANGRY;
  return ST_UNKNOWN;
}

static String extractStateField(const String &body) {
  const String key = "\"state\":\"";
  int i = body.indexOf(key);
  if (i < 0)
    return "";
  i += key.length();
  int j = body.indexOf('"', i);
  if (j < 0)
    return "";
  return body.substring(i, j);
}

void applyStateHardware(ClockState st) {
  // TODO: servos / tone() / OLED / I2C to a second MCU, etc.
  switch (st) {
    case ST_NEUTRAL:      Serial.println(F("[clock] neutral")); break;
    case ST_AT_EASE:      Serial.println(F("[clock] at_ease")); break;
    case ST_JOYFUL:       Serial.println(F("[clock] joyful")); break;
    case ST_SURPRISED:    Serial.println(F("[clock] surprised")); break;
    case ST_ANXIOUS:      Serial.println(F("[clock] anxious")); break;
    case ST_EMBARRASSED:  Serial.println(F("[clock] embarrassed")); break;
    case ST_ANGRY:        Serial.println(F("[clock] angry")); break;
    default:              Serial.println(F("[clock] ?")); break;
  }
}

#if defined(ARDUINO_ARCH_ESP32)

static int httpGetFullUrl(const char *fullUrl, String &outBody) {
  outBody = "";
  String url(fullUrl);

  WiFiClientSecure *secure = nullptr;
  WiFiClient *plain = nullptr;
  HTTPClient http;
  http.setTimeout(15000);

  int code;

  if (url.startsWith("https://")) {
    secure = new WiFiClientSecure;
    secure->setInsecure();
    http.begin(*secure, fullUrl);
    http.addHeader(SKIP_WARN_NAME, SKIP_WARN_VALUE);
    http.addHeader("User-Agent", "ESP32-Clock/1");
    code = http.GET();
    if (code == HTTP_CODE_OK)
      outBody = http.getString();
    http.end();
    delete secure;
    return code;
  }

  if (url.startsWith("http://")) {
    plain = new WiFiClient;
    http.begin(*plain, fullUrl);
    http.addHeader("User-Agent", "ESP32-Clock/1");
    code = http.GET();
    if (code == HTTP_CODE_OK)
      outBody = http.getString();
    http.end();
    delete plain;
    return code;
  }

  Serial.println(F("[ESP32] STATE_URL must start with http:// or https://"));
  return -99;
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(150);
  Serial.println();
  Serial.println(F("ESP32 clock bridge — polls /state"));

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print(F("Connecting Wi‑Fi"));
  unsigned t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 30000UL) {
    delay(300);
    Serial.print('.');
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("Wi‑Fi FAILED: check SSID/password"));
    return;
  }

  Serial.print(F("Wi‑Fi OK, IP: "));
  Serial.println(WiFi.localIP());
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("Wi‑Fi lost — reconnect"));
    WiFi.reconnect();
    delay(POLL_MS);
    return;
  }

  String body;
  int code = httpGetFullUrl(STATE_URL, body);

  if (code != HTTP_CODE_OK) {
    Serial.print(F("GET failed: "));
    Serial.println(code);
    delay(POLL_MS);
    return;
  }

  String st = extractStateField(body);
  if (!st.length()) {
    Serial.println(F("No \"state\" in JSON"));
    Serial.println(body.substring(0, 200));  // peek
    delay(POLL_MS);
    return;
  }

  if (st != g_lastRawState) {
    g_lastRawState = st;
    Serial.print(F("REMOTE state: "));
    Serial.println(st);
    applyStateHardware(parseStateEnum(st));
  }

  delay(POLL_MS);
}

#endif /* ARDUINO_ARCH_ESP32 */

/*
 * ---- If you insist on Arduino UNO with NO laptop cable ----------------------------
 *
 * A) Easiest wireless path: BUY an ESP32 (~$8). Use THIS sketch — it replaces
 *    bridge.py. You can STILL hang servos/displays off the ESP32 I/O pins,
 *    or use I2C/SPI/UART from ESP32 → UNO.
 *
 * B) HC-05 / HC-06 Bluetooth UART on UNO → pair with LAPTOP bluetooth → Python
 *    bridge.py prints to RFCOMM pseudo-serial (/dev/tty.BLTH…) instead of USB.
 *    Laptop must stay powered and paired (still "no USB to UNO", but BLE link).
 *
 * C) Separate tiny computer (Pi, phone USB-OTG…) running bridge.py near clock.
 */
