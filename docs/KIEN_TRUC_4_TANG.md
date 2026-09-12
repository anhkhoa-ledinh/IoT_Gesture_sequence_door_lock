# Kiến trúc 4 tầng

**Đề tài:** AI Hand-Gesture Authenticated Smart Door Lock — A Four-Layer IoT System
Using MediaPipe Hand Landmark Classification and MQTT

---

## 1. Tổng quan

Hệ thống gồm **hai thiết bị vật lý tách rời** nói chuyện với nhau hoàn toàn qua mạng:

```
┌─ TẦNG 4 — APPLICATION ──────────────────────────────────────────────┐
│  Node-RED Dashboard (trình duyệt, cổng 1880/ui)                     │
│  • Trạng thái ổ khóa (chữ to, đổi màu)                              │
│  • Trạng thái kết nối ESP32                                         │
│  • Bảng 10 lần truy cập gần nhất                                    │
│  • Nút "MỞ KHẨN CẤP"  ← sinh ra luồng downlink thứ hai              │
│  • Nút "RESET LOCKOUT"                                              │
│  • Biểu đồ số lần thành công / thất bại                             │
└───────────────────────────▲──────────────────┬──────────────────────┘
                            │ dữ liệu hiển thị │ thao tác người dùng
┌─ TẦNG 3 — MIDDLEWARE ─────┴──────────────────▼──────────────────────┐
│  Node-RED (middleware/flows.json)                                   │
│  • So mã nhận được với mã hợp lệ giữ trong flow context             │
│  • Đếm số lần sai liên tiếp, kích hoạt lockout 30 giây              │
│  • Ghi middleware/access_log.csv                                    │
│  • Watchdog: quá 15 giây không nghe ESP32 thì báo mất kết nối       │
└───────────────────────────▲──────────────────┬──────────────────────┘
                     uplink │                  │ downlink
┌─ TẦNG 2 — NETWORK ────────┴──────────────────▼──────────────────────┐
│  MQTT — broker.hivemq.com:1883, không xác thực                      │
│  Prefix topic: ueh/ak_majespecter/gate/                             │
└──────▲──────────────────────────────────────────────▲───────────────┘
       │ publish                          subscribe   │ publish
┌──────┴──────────────────────┐      ┌────────────────┴───────────────┐
│ TẦNG 1a — SENSING (laptop)  │      │ TẦNG 1b — ACTUATING (ESP32)    │
│ webcam + MediaPipe + MLP    │      │ servo GPIO18, OLED I2C 21/22,  │
│ vision/gesture_lock.py      │      │ buzzer GPIO5, LED 25/26        │
│                             │      │ firmware/gate_lock.ino (Wokwi) │
└─────────────────────────────┘      └────────────────────────────────┘
```

---

## 2. Từng tầng làm gì

### Tầng 1a — Sensing (laptop + webcam)

Chạy `vision/gesture_lock.py`. Ba thành phần tách rời:

| Thành phần | Nhiệm vụ |
|---|---|
| `GestureClassifier` | ảnh → `(tên lớp, độ tin cậy)`. Bên trong: MediaPipe HandLandmarker lấy 21 điểm mốc → `preprocess_landmarks()` chuẩn hóa thành vector 42 chiều → MLP dạng TFLite phân loại. |
| `SequenceStateMachine` | `(tên lớp, độ tin cậy)` mỗi khung → sự kiện "đã nhận 1 cử chỉ" / "đủ chuỗi 3 cử chỉ". Chỉ chấp nhận khi độ tin cậy ≥ 0.70 và giữ nguyên 15 khung liên tiếp. |
| `MqttPublisher` | sự kiện → bản tin MQTT. Chạy trên luồng riêng nên không làm treo vòng lặp camera. |

**Tầng này không tự quyết định gì.** Nó chỉ nói "người dùng vừa nhập mã E17C4D",
còn mã đó đúng hay sai là việc của tầng 3. Đây là chủ ý: nếu Python tự chặn mã sai
thì Node-RED không bao giờ đếm được số lần sai và cơ chế lockout sẽ vô dụng.

### Tầng 1b — Actuating (ESP32 mô phỏng trên Wokwi)

Chạy `firmware/gate_lock.ino`. ESP32 **chỉ nghe lệnh và thi hành**, không tự quyết định:

| Lệnh nhận được | ESP32 làm gì |
|---|---|
| `unlock` | servo quay 90°, LED xanh sáng, OLED "ACCESS GRANTED", 1 tiếng bíp ngắn. Sau `ttl` giây tự về 0°. |
| `deny` | LED đỏ nháy 3 lần, 2 tiếng bíp, OLED "ACCESS DENIED". |
| `lockout` | OLED đếm ngược `sec` giây, LED đỏ sáng liên tục, **bỏ qua mọi lệnh `unlock`** trong thời gian đó. |

Ngoài ra ESP32 còn nghe topic `.../gesture` để hiện chuỗi đang nhập dạng `E1 7C __`
lên OLED — chỉ để hiển thị, không điều khiển gì.

Toàn bộ firmware chạy bằng `millis()`, **không có một lệnh `delay()` nào**. Nếu chặn
`loop()` thì MQTT sẽ rớt kết nối và servo phản ứng trễ.

### Tầng 2 — Network (MQTT)

Broker công cộng `broker.hivemq.com:1883`, không xác thực. Mọi thiết bị chỉ cần biết
tên topic là nói chuyện được với nhau, không cần biết địa chỉ IP của nhau — đây chính
là điểm mạnh của mô hình publish/subscribe.

### Tầng 3 — Middleware (Node-RED)

Đây là nơi **ra quyết định**. Nhận mã từ tầng 1a, so với mã hợp lệ, rồi ra lệnh cho
tầng 1b. Đồng thời đếm số lần sai và ghi log.

### Tầng 4 — Application (Node-RED Dashboard)

Giao diện cho người dùng cuối: xem trạng thái, xem lịch sử, và can thiệp thủ công
bằng hai nút bấm.

---

## 3. Luồng uplink và downlink cụ thể

### 3.1. Uplink — từ thiết bị lên hệ thống

| # | Topic | Ai publish | Ai subscribe | Khi nào |
|---|---|---|---|---|
| U1 | `ueh/ak_majespecter/gate/gesture` | laptop (Python) | ESP32 | mỗi khi chấp nhận 1 cử chỉ |
| U2 | `ueh/ak_majespecter/gate/sequence` | laptop (Python) | Node-RED | khi đủ 3 cử chỉ |
| U3 | `ueh/ak_majespecter/gate/state` | ESP32 | Node-RED | mỗi 5 giây **và** mỗi khi đổi trạng thái |

**Luồng uplink chính là U2.** Đây là luồng mang dữ liệu cảm biến đã xử lý đi lên
tầng ra quyết định:

```
người dùng làm 3 cử chỉ
  -> webcam bắt được
  -> MediaPipe trích 21 điểm mốc
  -> MLP phân loại thành victory / palm / ok
  -> ghép thành "E17C4D"
  -> publish ueh/ak_majespecter/gate/sequence
  -> Node-RED nhận và kiểm mã
```

### 3.2. Downlink — từ hệ thống xuống thiết bị

| # | Topic | Ai publish | Ai subscribe | Khi nào |
|---|---|---|---|---|
| D1 | `ueh/ak_majespecter/gate/cmd` | Node-RED (function kiểm mã) | ESP32 | sau mỗi lần kiểm mã |
| D2 | `ueh/ak_majespecter/gate/cmd` | Node-RED (nút Dashboard) | ESP32 | khi bấm "MỞ KHẨN CẤP" hoặc "RESET LOCKOUT" |

**Luồng downlink chính là D1:**

```
Node-RED so "E17C4D" với mã hợp lệ
  -> khớp
  -> publish ueh/ak_majespecter/gate/cmd  {"action":"unlock","ttl":5}
  -> ESP32 nhận, quay servo 90 độ, bật LED xanh
  -> sau 5 giây servo tự về 0 độ
```

**Luồng downlink thứ hai là D2** — bắt nguồn từ tầng 4 chứ không phải tầng 3, đi
thẳng xuống tầng 1b mà không qua khâu nhận diện cử chỉ. Dùng khi camera hỏng hoặc
người dùng không làm được cử chỉ.

### 3.3. Một vòng hoàn chỉnh

```
[T1a laptop]  --U2 sequence-->  [T2 MQTT]  -->  [T3 Node-RED]
                                                      |
                                                 kiểm mã
                                                      |
[T1b ESP32]   <--D1 cmd-------  [T2 MQTT]  <----------┘
      |
      └--U3 state-->  [T2 MQTT]  -->  [T3 Node-RED]  -->  [T4 Dashboard]
```

Vòng này chứng minh hệ thống có đủ cả hai chiều, không phải chỉ là thiết bị đẩy
dữ liệu lên một chiều.

---

## 4. Vì sao bắt buộc phải tách hai máy

Đây là điểm hay bị hỏi nhất khi bảo vệ đồ án. Có **ba** lý do, lý do thứ ba là lý do
kỹ thuật bắt buộc:

### 4.1. ESP32 không chạy nổi MediaPipe

MediaPipe HandLandmarker cần khoảng 7.6 MB cho riêng file model, chưa kể bộ nhớ lúc
chạy. ESP32 có 520 KB SRAM và thường 4 MB flash. Chênh nhau hơn một bậc độ lớn —
không có cách nào nhét vừa. Việc nhận dạng **bắt buộc** phải làm trên máy mạnh hơn.

### 4.2. Đây mới đúng là mô hình IoT

Trong hệ IoT thật, node cảm biến và node chấp hành là hai thiết bị khác nhau, đặt ở
hai chỗ khác nhau, chỉ liên hệ qua mạng. Nếu gộp camera và servo vào một máy thì đó
là một thiết bị nhúng đơn lẻ, không còn là hệ thống phân tán và tầng 2 (Network) trở
nên vô nghĩa.

Cách tách này còn cho phép **một Node-RED quản lý nhiều cửa**: thêm cửa thứ hai chỉ
cần đổi prefix topic, không phải sửa code.

### 4.3. Wokwi chạy trên cloud, không thấy được localhost của bạn

Đây là ràng buộc kỹ thuật cứng. ESP32 mô phỏng chạy **trên máy chủ của Wokwi**, không
chạy trên máy bạn. Nó không có đường nào tới `localhost` hay `192.168.x.x` của bạn.

Hệ quả trực tiếp: **phải dùng broker MQTT công cộng**. Một broker cài trên máy bạn
(Mosquitto local) sẽ không bao giờ kết nối được với Wokwi. Đó là lý do dự án dùng
`broker.hivemq.com` chứ không tự dựng broker.

```
            Internet
                │
    ┌───────────┼───────────┐
    │           │           │
[laptop]  [broker.hivemq]  [Wokwi cloud]
 Python      công cộng        ESP32
```

**Đánh đổi phải nêu trong báo cáo:** broker công cộng không có xác thực, ai biết tên
topic đều nghe và gửi lệnh được. Trong hệ thật phải dùng broker riêng có TLS và
tài khoản. Ở đồ án này ta chấp nhận đánh đổi đó để chạy được với Wokwi, và bù lại
bằng hai biện pháp phòng thủ ở phía thiết bị:

1. **Client ID ngẫu nhiên** ở cả ESP32 lẫn Python — tránh trùng ID với người lạ
   trên broker công cộng gây đá kết nối lẫn nhau.
2. **Lockout được chặn ở tầng firmware, không chỉ ở Node-RED** — kể cả có người
   publish thẳng lệnh `unlock` vào broker trong lúc đang lockout, ESP32 vẫn từ chối.

---

## 5. Bảng tóm tắt công nghệ từng tầng

| Tầng | Thành phần | Công nghệ | File |
|---|---|---|---|
| 1a | Node cảm biến | Python, OpenCV, MediaPipe Tasks, TFLite | `vision/gesture_lock.py` |
| 1b | Node chấp hành | ESP32 Arduino, PubSubClient, ESP32Servo, Adafruit SSD1306 | `firmware/gate_lock.ino` |
| 2 | Truyền thông | MQTT 3.1.1 qua TCP 1883 | — |
| 3 | Middleware | Node-RED, function node JavaScript | `middleware/flows.json` |
| 4 | Giao diện | node-red-dashboard | cùng file `flows.json` |
