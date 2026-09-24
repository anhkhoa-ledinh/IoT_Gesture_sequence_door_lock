/*
 * ============================================================================
 *  gate_lock.ino  —  TANG 1b: NODE CHAP HANH (ESP32)
 *  De tai: AI Hand-Gesture Authenticated Smart Door Lock (he thong IoT 4 tang)
 * ----------------------------------------------------------------------------
 *  ESP32 la mot thiet bi DOC LAP voi laptop chay Python. Hai ben khong noi
 *  chuyen truc tiep, tat ca di qua MQTT (broker.hivemq.com).
 *
 *  ESP32 lam 3 viec:
 *    1. Subscribe .../cmd     <- nhan lenh unlock / deny / lockout tu Node-RED
 *    2. Subscribe .../gesture <- nhan tung cu chi de hien chuoi dang nhap len OLED
 *    3. Publish  .../state    -> bao trang thai khoa len he thong (moi 5s + khi doi)
 *
 *  NGUYEN TAC: TOAN BO dung millis(). KHONG co delay() o bat ky dau trong file
 *  nay. Neu chan loop() thi MQTT se rot ket noi va servo se tre.
 * ============================================================================
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ============================================================================
//  1. CHAN PHAN CUNG  (muc 2.2 cua spec — phai khop firmware/diagram.json)
// ============================================================================
static const uint8_t PIN_SERVO     = 18;  // Servo SG90
static const uint8_t PIN_OLED_SDA  = 21;  // OLED SSD1306 I2C - SDA
static const uint8_t PIN_OLED_SCL  = 22;  // OLED SSD1306 I2C - SCL
static const uint8_t PIN_BUZZER    =  5;  // Buzzer
static const uint8_t PIN_LED_GREEN = 25;  // LED xanh - mo khoa
static const uint8_t PIN_LED_RED   = 26;  // LED do   - tu choi / lockout

// ============================================================================
//  2. MANG VA MQTT
// ============================================================================
static const char* WIFI_SSID    = "Wokwi-GUEST";
static const char* WIFI_PASS    = "";   // Wokwi-GUEST khong co mat khau
static const int   WIFI_CHANNEL = 6;

static const char*    MQTT_HOST = "broker.hivemq.com";
static const uint16_t MQTT_PORT = 1883;

// TODO: doi "ak_majespecter" thanh MSSV that. Phai sua dong bo 3 noi:
//       vision/config.json  |  firmware/gate_lock.ino (day)  |  middleware/flows.json
#define TOPIC_PREFIX "huit/ak_majespecter/gate/"
static const char* TOPIC_CMD     = TOPIC_PREFIX "cmd";      // downlink: Node-RED -> ESP32
static const char* TOPIC_GESTURE = TOPIC_PREFIX "gesture";  // uplink  : Python  -> broker
static const char* TOPIC_STATE   = TOPIC_PREFIX "state";    // uplink  : ESP32   -> broker

// ============================================================================
//  3. NGUONG  (muc 2.4 cua spec — phai khop vision/config.json)
// ============================================================================
static const int SERVO_CLOSED_DEG = 0;    // goc servo khi khoa
static const int SERVO_OPEN_DEG   = 90;   // goc servo khi mo

static const unsigned long STATE_PERIOD_MS       = 5000;   // chu ky publish .../state
static const unsigned long SEQ_DISPLAY_TIMEOUT_MS = 10000; // chuoi hex tu xoa sau 10s im lang
static const unsigned long WIFI_RETRY_MS         = 5000;   // gian cach thu lai WiFi
static const unsigned long MQTT_RETRY_MS         = 3000;   // gian cach thu lai MQTT
static const unsigned long DISPLAY_REFRESH_MS    = 120;    // chu ky ve lai OLED
static const unsigned long DENY_MSG_MS           = 2000;   // giu chu DENIED bao lau

static const uint8_t CODE_LEN = 3;  // do dai ma = 3 cu chi

// ============================================================================
//  4. BIEN TRANG THAI TOAN CUC
// ============================================================================
WiFiClient       wifiClient;
PubSubClient     mqtt(wifiClient);
Servo            gateServo;
Adafruit_SSD1306 display(128, 64, &Wire, -1);

// Trang thai khoa. LOCK_LOCKOUT co do uu tien cao nhat.
enum LockState { LOCK_CLOSED, LOCK_OPEN, LOCK_LOCKOUT };
LockState lockState = LOCK_CLOSED;

unsigned long unlockUntilMs  = 0;  // moc thoi gian servo tu dong dong lai
unsigned long lockoutUntilMs = 0;  // moc thoi gian het lockout
unsigned long denyMsgUntilMs = 0;  // moc thoi gian tat chu DENIED
uint32_t      denyAttempts   = 0;  // so lan bi tu choi lien tiep (theo goc nhin ESP32)
bool          oledOk         = false;

unsigned long nextWifiTryMs    = 0;
unsigned long nextMqttTryMs    = 0;
unsigned long nextStatePubMs   = 0;
unsigned long nextDisplayMs    = 0;

// Chuoi hex dang nhap, hien len OLED dang "E1 7C __"
char          codeSlots[CODE_LEN][3];  // moi o giu 2 ky tu hex + '\0'
uint8_t       codeCount    = 0;
unsigned long lastGestureMs = 0;

// ---- Bo phat tieng bip khong chan (buzzer state machine) ----
struct BeepPlan {
  uint8_t       remaining;   // so tieng con phai keu
  uint16_t      onMs;        // thoi gian keu moi tieng
  uint16_t      offMs;       // thoi gian nghi giua 2 tieng
  uint16_t      freq;        // tan so
  bool          soundOn;     // dang keu hay khong
  unsigned long nextChangeMs;// moc doi trang thai ke tiep
};
BeepPlan beep = {0, 0, 0, 0, false, 0};

// ---- Bo nhay LED do khong chan (blink state machine) ----
struct BlinkPlan {
  uint8_t       remaining;    // so lan nhay con lai
  uint16_t      halfPeriodMs; // nua chu ky (sang hoac tat)
  bool          ledOn;
  unsigned long nextChangeMs;
};
BlinkPlan redBlink = {0, 0, false, 0};

// ============================================================================
//  5. KHAI BAO TRUOC
//  Arduino tu sinh prototype, nhung khai bao ro rang thi trinh bien dich nao
//  cung chay duoc va doc code de theo hon.
// ============================================================================
void setupHardware();
void updateWifi();
void updateMqtt();
void onMqttMessage(char* topic, byte* payload, unsigned int length);
void publishState();
void applyUnlock(unsigned long ttlSec);
void applyDeny();
void applyLockout(unsigned long sec);
void updateTimers();
void updateBuzzer();
void updateLeds();
void updateDisplay();

// ============================================================================
//  6. TIEN ICH
// ============================================================================

// So sanh moc thoi gian an toan voi tran so millis() (sau ~49 ngay).
static inline bool timeReached(unsigned long deadline) {
  return (long)(millis() - deadline) >= 0;
}

// Dat lich keu n tieng bip. Khong chan, viec keu do updateBuzzer() lo.
void startBeeps(uint8_t times, uint16_t onMs, uint16_t offMs, uint16_t freq) {
  beep.remaining    = times;
  beep.onMs         = onMs;
  beep.offMs        = offMs;
  beep.freq         = freq;
  beep.soundOn      = false;
  beep.nextChangeMs = millis();
}

// Dat lich nhay LED do n lan. Khong chan.
void startRedBlink(uint8_t times, uint16_t halfPeriodMs) {
  redBlink.remaining    = times * 2;  // moi lan nhay = 1 sang + 1 tat
  redBlink.halfPeriodMs = halfPeriodMs;
  redBlink.ledOn        = false;
  redBlink.nextChangeMs = millis();
}

// Xoa chuoi hex dang hien tren OLED.
void clearCodeDisplay() {
  codeCount = 0;
}

// ============================================================================
//  6. KHOI TAO PHAN CUNG
// ============================================================================
void setupHardware() {
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_RED,   OUTPUT);
  digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_RED,   LOW);
  pinMode(PIN_BUZZER, OUTPUT);

  // ESP32Servo va tone() cung dung bo LEDC. Chi cap 2 timer cho servo de
  // con timer trong cho tone() dieu khien buzzer, tranh giành tài nguyên.
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  gateServo.setPeriodHertz(50);                 // SG90 chay o 50 Hz
  gateServo.attach(PIN_SERVO, 500, 2400);       // do rong xung 0.5ms - 2.4ms
  gateServo.write(SERVO_CLOSED_DEG);            // khoi dong o trang thai KHOA

  Wire.begin(PIN_OLED_SDA, PIN_OLED_SCL);
  oledOk = display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  if (oledOk) {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("GATE LOCK");
    display.println("dang khoi dong...");
    display.display();
  }
}

// ============================================================================
//  7. WIFI — khong chan
// ============================================================================
void updateWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  if (!timeReached(nextWifiTryMs)) return;

  nextWifiTryMs = millis() + WIFI_RETRY_MS;
  // Wokwi-GUEST bat buoc chi ro channel 6 thi moi bat nhanh.
  WiFi.begin(WIFI_SSID, WIFI_PASS, WIFI_CHANNEL);
}

// ============================================================================
//  8. MQTT — ket noi lai khong chan + xu ly ban tin den
// ============================================================================

// Nhan lenh tu .../cmd va cu chi tu .../gesture.
void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, length) != DeserializationError::Ok) {
    return;  // JSON hong thi bo qua, khong lam sap firmware
  }

  // ---- .../gesture : chi de hien thi, khong dieu khien gi ----
  if (strcmp(topic, TOPIC_GESTURE) == 0) {
    const char* hex = doc["hex"] | "";
    if (strlen(hex) == 2) {
      if (codeCount >= CODE_LEN) codeCount = 0;   // chuoi moi bat dau
      codeSlots[codeCount][0] = hex[0];
      codeSlots[codeCount][1] = hex[1];
      codeSlots[codeCount][2] = '\0';
      codeCount++;
      lastGestureMs = millis();
    }
    return;
  }

  // ---- .../cmd : lenh dieu khien that ----
  if (strcmp(topic, TOPIC_CMD) != 0) return;

  const char* action = doc["action"] | "";

  // Dang lockout thi BO QUA moi lenh unlock (yeu cau bao mat cua spec).
  if (lockState == LOCK_LOCKOUT && !timeReached(lockoutUntilMs)
      && strcmp(action, "unlock") == 0) {
    startBeeps(1, 60, 60, 400);   // bip tram bao "dang bi khoa"
    return;
  }

  if (strcmp(action, "unlock") == 0) {
    unsigned long ttl = doc["ttl"] | 5;   // giay giu mo, mac dinh 5
    applyUnlock(ttl);
  } else if (strcmp(action, "deny") == 0) {
    applyDeny();
  } else if (strcmp(action, "lockout") == 0) {
    unsigned long sec = doc["sec"] | 30;  // giay lockout, mac dinh 30
    applyLockout(sec);
  }
}

void updateMqtt() {
  if (WiFi.status() != WL_CONNECTED) return;

  if (mqtt.connected()) {
    mqtt.loop();
    return;
  }

  if (!timeReached(nextMqttTryMs)) return;
  nextMqttTryMs = millis() + MQTT_RETRY_MS;

  // Client ID ngau nhien: broker.hivemq.com la broker CONG CONG, neu trung ID
  // voi may khac thi hai ben se da nhau va lien tuc bi ngat ket noi.
  // random() da duoc gieo bang MAC chip trong setup() nen moi board mot khac.
  char clientId[32];
  snprintf(clientId, sizeof(clientId), "esp32-gate-%04lX%04lX",
           (unsigned long)random(0x10000), (unsigned long)random(0x10000));

  if (mqtt.connect(clientId)) {
    mqtt.subscribe(TOPIC_CMD);
    mqtt.subscribe(TOPIC_GESTURE);
    publishState();   // bao trang thai ngay khi vua noi lai duoc
  }
}

// Publish .../state — payload dung 3 truong theo spec muc 2.1.
void publishState() {
  // Doi han dinh ky TRUOC khi kiem tra ket noi: neu dang mat MQTT ma khong
  // doi han thi updateTimers() se goi lai ham nay moi vong loop.
  nextStatePubMs = millis() + STATE_PERIOD_MS;
  if (!mqtt.connected()) return;

  const char* lockText = "closed";
  if (lockState == LOCK_OPEN)         lockText = "open";
  else if (lockState == LOCK_LOCKOUT) lockText = "lockout";

  JsonDocument doc;
  doc["lock"]     = lockText;
  doc["attempts"] = denyAttempts;
  doc["uptime"]   = millis() / 1000;

  char buf[128];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  mqtt.publish(TOPIC_STATE, (const uint8_t*)buf, n, false);
}

// ============================================================================
//  9. BA HANH DONG: unlock / deny / lockout
// ============================================================================

// MO KHOA: servo 90 do, LED xanh, OLED "ACCESS GRANTED", 1 tieng bip ngan.
// Sau ttl giay tu dong ve 0 do.
void applyUnlock(unsigned long ttlSec) {
  lockState      = LOCK_OPEN;
  unlockUntilMs  = millis() + ttlSec * 1000UL;
  denyAttempts   = 0;             // mo duoc thi xoa bo dem sai
  denyMsgUntilMs = 0;
  redBlink.remaining = 0;

  gateServo.write(SERVO_OPEN_DEG);
  startBeeps(1, 120, 80, 1800);   // 1 tieng ngan, cao
  clearCodeDisplay();
  publishState();
}

// TU CHOI: LED do nhay 3 lan, 2 tieng bip, OLED "DENIED".
void applyDeny() {
  denyAttempts++;
  denyMsgUntilMs = millis() + DENY_MSG_MS;

  startRedBlink(3, 150);
  startBeeps(2, 150, 120, 700);
  clearCodeDisplay();
  publishState();
}

// LOCKOUT: OLED dem nguoc, LED do sang lien tuc, bo qua moi lenh unlock.
void applyLockout(unsigned long sec) {
  lockState      = LOCK_LOCKOUT;
  lockoutUntilMs = millis() + sec * 1000UL;
  denyMsgUntilMs = 0;
  redBlink.remaining = 0;         // lockout thi LED do sang lien tuc, khong nhay

  gateServo.write(SERVO_CLOSED_DEG);
  startBeeps(3, 250, 150, 500);   // 3 tieng dai, tram
  clearCodeDisplay();
  publishState();
}

// ============================================================================
//  10. CAC BO CAP NHAT THEO THOI GIAN (goi moi vong loop)
// ============================================================================

// Servo tu dong dong lai sau ttl; lockout tu het han.
void updateTimers() {
  if (lockState == LOCK_OPEN && timeReached(unlockUntilMs)) {
    lockState = LOCK_CLOSED;
    gateServo.write(SERVO_CLOSED_DEG);
    publishState();
  }

  if (lockState == LOCK_LOCKOUT && timeReached(lockoutUntilMs)) {
    lockState    = LOCK_CLOSED;
    denyAttempts = 0;             // het phat thi cho lam lai tu dau
    publishState();
  }

  // Chuoi hex dang nhap tu xoa neu im lang qua lau.
  if (codeCount > 0 && timeReached(lastGestureMs + SEQ_DISPLAY_TIMEOUT_MS)) {
    clearCodeDisplay();
  }

  // Publish dinh ky moi 5 giay.
  if (timeReached(nextStatePubMs)) {
    publishState();
  }
}

// Buzzer: doi giua keu / nghi theo lich, khong chan CPU.
void updateBuzzer() {
  if (beep.remaining == 0 && !beep.soundOn) return;
  if (!timeReached(beep.nextChangeMs)) return;

  if (beep.soundOn) {
    noTone(PIN_BUZZER);
    beep.soundOn      = false;
    beep.nextChangeMs = millis() + beep.offMs;
  } else {
    tone(PIN_BUZZER, beep.freq);
    beep.soundOn      = true;
    beep.remaining--;
    beep.nextChangeMs = millis() + beep.onMs;
  }
}

// LED: xanh sang khi mo; do sang lien tuc khi lockout, nhay khi bi tu choi.
void updateLeds() {
  digitalWrite(PIN_LED_GREEN, lockState == LOCK_OPEN ? HIGH : LOW);

  if (lockState == LOCK_LOCKOUT) {
    digitalWrite(PIN_LED_RED, HIGH);   // lockout uu tien cao nhat
    return;
  }

  if (redBlink.remaining > 0) {
    if (timeReached(redBlink.nextChangeMs)) {
      redBlink.ledOn        = !redBlink.ledOn;
      redBlink.remaining--;
      redBlink.nextChangeMs = millis() + redBlink.halfPeriodMs;
    }
    digitalWrite(PIN_LED_RED, redBlink.ledOn ? HIGH : LOW);
    return;
  }

  digitalWrite(PIN_LED_RED, LOW);
}

// Man hinh cho: WiFi/MQTT, trang thai khoa, chuoi dang nhap, dem nguoc.
void updateDisplay() {
  if (!oledOk) return;
  if (!timeReached(nextDisplayMs)) return;
  nextDisplayMs = millis() + DISPLAY_REFRESH_MS;

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  // --- Dong 1: trang thai ket noi ---
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print("WiFi:");
  display.print(WiFi.status() == WL_CONNECTED ? "OK" : "--");
  display.print("  MQTT:");
  display.print(mqtt.connected() ? "OK" : "--");

  // --- Dong 2: thong bao ---
  display.setCursor(0, 12);
  if (lockState == LOCK_OPEN) {
    display.print("ACCESS GRANTED");
  } else if (lockState == LOCK_LOCKOUT) {
    display.print("TOO MANY TRIES");
  } else if (!timeReached(denyMsgUntilMs)) {
    display.print("ACCESS DENIED");
  } else {
    display.print("READY - show code");
  }

  // --- Dong 3: trang thai khoa, chu to ---
  display.setTextSize(2);
  display.setCursor(0, 24);
  if (lockState == LOCK_OPEN)         display.print("OPEN");
  else if (lockState == LOCK_LOCKOUT) display.print("LOCKOUT");
  else if (!timeReached(denyMsgUntilMs)) display.print("DENIED");
  else                                display.print("LOCKED");

  // --- Dong 4: chuoi hex dang nhap dang "E1 7C __" ---
  display.setTextSize(1);
  display.setCursor(0, 44);
  display.print("CODE ");
  for (uint8_t i = 0; i < CODE_LEN; i++) {
    display.print(i < codeCount ? codeSlots[i] : "__");
    if (i < CODE_LEN - 1) display.print(' ');
  }

  // --- Dong 5: dem nguoc / so lan sai ---
  display.setCursor(0, 55);
  if (lockState == LOCK_LOCKOUT) {
    long remain = ((long)(lockoutUntilMs - millis()) + 999) / 1000;
    if (remain < 0) remain = 0;
    display.print("Khoa them ");
    display.print(remain);
    display.print("s");
  } else if (lockState == LOCK_OPEN) {
    long remain = ((long)(unlockUntilMs - millis()) + 999) / 1000;
    if (remain < 0) remain = 0;
    display.print("Tu dong dong sau ");
    display.print(remain);
    display.print("s");
  } else {
    display.print("So lan sai: ");
    display.print(denyAttempts);
  }

  display.display();
}

// ============================================================================
//  11. SETUP / LOOP
// ============================================================================
void setup() {
  Serial.begin(115200);

  // Gieo bo sinh so ngau nhien bang MAC chip (duy nhat moi board) tron voi
  // micros(), de client ID MQTT khong lap lai giua cac lan chay.
  randomSeed((uint32_t)ESP.getEfuseMac() ^ micros());

  setupHardware();

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS, WIFI_CHANNEL);
  nextWifiTryMs = millis() + WIFI_RETRY_MS;

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);
  nextMqttTryMs  = millis();
  nextStatePubMs = millis() + STATE_PERIOD_MS;
  nextDisplayMs  = millis();
}

void loop() {
  // Moi ham deu tra ve ngay neu chua den han. Khong ham nao chan CPU.
  updateWifi();
  updateMqtt();
  updateTimers();
  updateBuzzer();
  updateLeds();
  updateDisplay();
}
