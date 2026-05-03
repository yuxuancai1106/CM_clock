/*
 * Arduino UNO R4 WiFi — poll Flask /state over HTTPS (NO laptop ↔ USB bridge)
 *
 * Boards like **Arduino UNO R4 WiFi** have Wi‑Fi (+ BLE LE) built in.
 * Same idea as bridge.py / the ESP32 sketch: HTTP GET `/state`, read JSON,
 * react when `"state"` changes.
 *
 * 1. In Arduino IDE: Board = "Arduino UNO R4 WiFi".
 * 2. Set WIFI SSID/PASSWORD and SERVER_HOST/PATH below.
 * 3. Your public URL MUST end with `/state` as the path — e.g. ngrok shows
 *    https://abc.ngrok-free.app  → SERVER_HOST = abc.ngrok-free.app
 *    SERVER_PATH = "/state"
 *
 * **UNO WiFi Rev2** (older, NINA‑W102 chip) uses *WiFiNINA*, not WiFiS3 —
 * ask if you need that sketch; logic is identical, library differs.
 */

#if !defined(ARDUINO_UNOR4_WIFI)
#error "Select Board: Arduino UNO R4 WiFi. (UNO WiFi Rev2 uses a different WiFi library.)"
#else

#include <WiFiS3.h>
#include <WiFiSSLClient.h>

// ---------- Wi‑Fi ------------------------------------------------------------
static const char *SSID = "YOUR_WIFI_SSID";
static const char *PASS = "YOUR_WIFI_PASSWORD";

// ---------- Server (HTTPS) ----------------------------------------------------
// ONLY host (no scheme, no path)
static const char *SERVER_HOST = "YOUR_SUBDOMAIN.ngrok-free.app";

// MUST start with '/'
static const char *SERVER_PATH = "/state";

static const unsigned long POLL_MS       = 500;
static const unsigned long CONNECT_TIMEOUT_MS = 20000;

// ----------------------------------------------------------------------------
static WiFiSSLClient ssl;
static String        g_lastState;

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

static bool findBodyAfterHeaders(const String &full, String &outBody) {
  int ix = full.indexOf("\r\n\r\n");
  if (ix < 0)
    ix = full.indexOf("\n\n");  // lenient
  if (ix < 0) {
    outBody = full;
    return false;
  }
  outBody = full.substring(ix + 4);
  return true;
}

static void reactTo(const String &emotion) {
  // TODO: servos / buzzer / I2C OLED here
  Serial.print(F("[uno-r4-wifi] state = "));
  Serial.println(emotion);
}

void setup() {
  Serial.begin(115200);
  for (unsigned t = millis(); millis() - t < 2500 && !Serial; )
    ;

  Serial.println(F("\nUno R4 WiFi → polling /state"));
  WiFi.begin(SSID, PASS);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < CONNECT_TIMEOUT_MS)
    delay(300);

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("Wi‑Fi FAILED: check SSID/password"));
    return;
  }

  Serial.print(F("Wi‑Fi OK, IP "));
  Serial.println(WiFi.localIP());
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("Wi‑Fi lost, reconnect…"));
    WiFi.begin(SSID, PASS);
    delay(1000);
    return;
  }

  ssl.stop();
  if (!ssl.connect(SERVER_HOST, 443)) {
    Serial.println(F("TLS connect failed"));
    delay(POLL_MS);
    return;
  }

  ssl.print(F("GET "));
  ssl.print(SERVER_PATH);
  ssl.println(F(" HTTP/1.1"));
  ssl.print(F("Host: "));
  ssl.println(SERVER_HOST);
  // ngrok-free: tell edge we are an API client, not a browser tab
  ssl.println(F("ngrok-skip-browser-warning: true"));
  ssl.println(F("User-Agent: Arduino-Uno-R4-WiFi-clock/1"));
  ssl.println(F("Connection: close"));
  ssl.println();

  unsigned long deadline = millis() + 15000;
  String      raw;

  while (ssl.connected() && millis() < deadline) {
    while (ssl.available()) {
      raw += static_cast<char>(ssl.read());
      if (raw.length() > 6000)
        break;
    }
    delay(1);
  }
  ssl.stop();

  String body;
  findBodyAfterHeaders(raw, body);

  if (body.length() == 0) {
    Serial.println(F("Empty body"));
    delay(POLL_MS);
    return;
  }

  String st = extractStateField(body);

  if (st.length() == 0) {
    Serial.println(F("No \"state\" in JSON"));
    int n = (int)body.length();
    if (n > 200)
      n = 200;
    Serial.println(body.substring(0, n));
    delay(POLL_MS);
    return;
  }

  if (st != g_lastState) {
    g_lastState = st;
    reactTo(st);
  }

  delay(POLL_MS);
}

#endif
