/*
 * Arduino UNO WiFi Rev 2 — HTTPS *client*: poll Flask GET /state
 *
 * The Karl Söderby tutorial hosts a tiny **web server** on the Arduino: you
 * open http://arduino-local-ip only on the *same LAN*.
 *
 * Your clock needs the opposite shape for attendees + LLM: Flask stays on the
 * internet (ngrok/Render/laptop); the board is an **HTTPS client** using the
 * same WiFiNINA stack as "WiFiSSLClient" in the Arduino examples library.
 *
 * Board: Arduino megaAVR Boards → Arduino UNO WiFi Rev 2  
 * Install **WiFiNINA**. Update NINA firmware if SSL fails (Arduino docs).
 *
 * Edit ssid/pass/serverHost/ngrok subdomain below.
 */
#include <SPI.h>
#include <WiFiNINA.h>
#include <WiFiSSLClient.h>

// ---- Wi‑Fi ---------------------------------------------------------------
char ssid[] = "";  // network SSID (case sensitive)
char pass[] = "";  // password

int wifiStatus = WL_IDLE_STATUS;

// HTTPS host ONLY (no https:// prefix)
char serverHost[] = "YOUR_SUBDOMAIN.ngrok-free.app";
// path with leading /
char serverPath[] = "/state";

static const unsigned long POLL_MS_MS = 600;

WiFiSSLClient ssl;
static String g_lastState;

#if !defined(WIFI_FIRMWARE_LATEST_VERSION)
#define WIFI_FIRMWARE_LATEST_VERSION "1.5.1"
#endif

static void printWifiStatus() {
  Serial.print(F("SSID: "));
  Serial.println(WiFi.SSID());
  Serial.print(F("IP: "));
  Serial.println(WiFi.localIP());
}

static bool connectWiFiOnce() {
  if (WiFi.status() == WL_NO_MODULE) {
    Serial.println(F("WiFi module failed!"));
    return false;
  }
  String fv = WiFi.firmwareVersion();
  if (fv < WIFI_FIRMWARE_LATEST_VERSION)
    Serial.println(F("(optional) Upgrade NINA firmware via IDE"));

  Serial.print(F("Connecting: "));
  Serial.println(ssid);
  wifiStatus = WiFi.begin(ssid, pass);
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 25000UL)
    delay(500);

  return WiFi.status() == WL_CONNECTED;
}

static String extractStateJson(const String &body) {
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

// Read HTTP response until header/body delimiter, accumulate body only (RAM cap).
static bool readBodyAfterHeaders(WiFiSSLClient &c, String &body, size_t maxBodyChars) {
  body        = "";
  String head = "";

  enum { PHASE_HEADERS, PHASE_BODY } phase = PHASE_HEADERS;
  unsigned long deadline = millis() + 20000UL;

  while (millis() < deadline) {
    while (c.available()) {
      char ch = static_cast<char>(c.read());

      if (phase == PHASE_HEADERS) {
        head += ch;
        if (head.length() > 3000)
          return false;

        const int delim = head.indexOf("\r\n\r\n");
        if (delim >= 0) {
          phase = PHASE_BODY;
          body  = head.substring(delim + 4);
          head  = "";
          if (body.length() >= maxBodyChars)
            return true;
        }
      } else {
        body += ch;
        if (body.length() >= maxBodyChars)
          return true;
      }

      yield();
    }

    if (!c.connected())
      break;
    delay(1);
  }

  return phase == PHASE_BODY && body.length() > 0;
}

static void reactToEmotion(const String &st) {
  // --- Your hardware HERE (LED, servo, DFPlayer …) ----------------------------
  Serial.print(F("[REV2 emotion] "));
  Serial.println(st);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  SPI.begin();  // NINA sits on SPI

  if (!connectWiFiOnce()) {
    Serial.println(F("WiFi connect failed"));
    return;
  }

  printWifiStatus();
  Serial.println(F("\nPolling /state over HTTPS …"));
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("Reconnecting WiFi …"));
    connectWiFiOnce();
    delay(POLL_MS_MS);
    return;
  }

  ssl.stop();

  if (!ssl.connect(serverHost, 443)) {
    Serial.println(F("TLS connect(host,443) failed"));
    delay(POLL_MS_MS);
    return;
  }

  ssl.print(F("GET "));
  ssl.print(serverPath);
  ssl.println(F(" HTTP/1.1"));
  ssl.print(F("Host: "));
  ssl.println(serverHost);
  ssl.println(F("ngrok-skip-browser-warning: true"));
  ssl.println(F("User-Agent: UnoWiFiRev2-clock/1"));
  ssl.println(F("Connection: close"));
  ssl.println();

  String body;
  bool ok = readBodyAfterHeaders(ssl, body, (size_t)640);
  ssl.stop();

  if (!ok) {
    Serial.println(F("HTTPS read failed"));
    delay(POLL_MS_MS);
    return;
  }

  String st = extractStateJson(body);
  if (!st.length()) {
    Serial.println(F("Can't find \\\"state\\\" JSON field"));
    int n = body.length();
    if (n > 160)
      n = 160;
    Serial.println(body.substring(0, n));
    delay(POLL_MS_MS);
    return;
  }

  if (st != g_lastState) {
    g_lastState = st;
    reactToEmotion(st);
  }

  delay(POLL_MS_MS);
}
