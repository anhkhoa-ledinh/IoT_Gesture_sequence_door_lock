# Bảng MQTT topic và payload

**Broker:** `broker.hivemq.com`  **Port:** `1883`  **Xác thực:** không
**Giao thức:** MQTT 3.1.1  **QoS:** 0  **Retain:** không

**Prefix topic:** `huit/ak_majespecter/gate/`

> **TODO — MSSV:** đang dùng `ak_majespecter` tạm. Khi có MSSV thật phải sửa **ba** nơi:
> 1. `mqtt.topic_prefix` trong `vision/config.json`
> 2. `#define TOPIC_PREFIX` trong `firmware/gate_lock.cpp`
> 3. hằng `TOPIC_CMD` trong các function node của `middleware/flows.json`

---

## 1. Bảng tổng hợp

| Topic | Hướng | Publisher | Subscriber | Tần suất |
|---|---|---|---|---|
| `.../gesture` | uplink | laptop (Python) | ESP32 | mỗi khi chấp nhận 1 cử chỉ |
| `.../sequence` | uplink | laptop (Python) | Node-RED | khi đủ 3 cử chỉ |
| `.../cmd` | **downlink** | Node-RED | ESP32 | sau mỗi lần kiểm mã, hoặc khi bấm nút Dashboard |
| `.../state` | uplink | ESP32 | Node-RED | mỗi 5 giây và mỗi khi đổi trạng thái |

---

## 2. `.../gesture` — uplink

**Đầy đủ:** `huit/ak_majespecter/gate/gesture`
**Publish bởi:** `MqttPublisher.publish_gesture()` trong `vision/gesture_lock.py`
**Mục đích:** báo vừa chấp nhận một cử chỉ. ESP32 nghe để hiện chuỗi đang nhập lên OLED.

### Payload

```json
{"gesture":"victory","hex":"E1","conf":0.93,"ts":1789220966}
```

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `gesture` | string | tên lớp cử chỉ: `fist` / `palm` / `victory` / `thumb_up` / `point_up` / `ok` |
| `hex` | string | 2 ký tự hex tương ứng, tra theo bảng mã |
| `conf` | number | độ tin cậy softmax, làm tròn 2 chữ số. Luôn ≥ 0.70 vì dưới ngưỡng thì không được chấp nhận |
| `ts` | number | Unix epoch giây |

### Ví dụ một chuỗi hoàn chỉnh

```json
{"gesture":"palm","hex":"7C","conf":0.97,"ts":1789220966}
{"gesture":"victory","hex":"E1","conf":0.93,"ts":1789220969}
{"gesture":"fist","hex":"3A","conf":0.88,"ts":1789220972}
```

> Ba payload trên là **định dạng thật** do code sinh ra (đã kiểm chứng), nhưng giá trị
> `conf` là minh họa — độ tin cậy thật **chưa đo được** vì chưa có model huấn luyện.

---

## 3. `.../sequence` — uplink, luồng uplink chính

**Đầy đủ:** `huit/ak_majespecter/gate/sequence`
**Publish bởi:** `MqttPublisher.publish_sequence()` trong `vision/gesture_lock.py`
**Subscribe bởi:** node `uplink .../sequence` trong `middleware/flows.json`

### Payload

```json
{"code":"7CE13A","ts":1789220972}
```

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `code` | string | 6 ký tự hex = 3 cử chỉ ghép lại |
| `ts` | number | Unix epoch giây |

**Quan trọng:** Python publish **mọi** chuỗi nhập đủ 3 cử chỉ, **kể cả chuỗi sai**.
Kiểm mã là việc của Node-RED. Nếu Python tự lọc thì Node-RED không đếm được số lần
sai và lockout sẽ không bao giờ kích hoạt.

Ví dụ chuỗi sai:

```json
{"code":"3A3A3A","ts":1789221010}
```

---

## 4. `.../cmd` — downlink

**Đầy đủ:** `huit/ak_majespecter/gate/cmd`
**Publish bởi:** function `Kiem ma`, `Lenh mo khan cap`, `Xoa lockout hai noi` trong Node-RED
**Subscribe bởi:** `onMqttMessage()` trong `firmware/gate_lock.cpp`

Có **ba** action. Payload dưới đây là output thật khi chạy hàm kiểm mã:

### 4.1. `unlock`

```json
{"action":"unlock","ttl":5}
```

| Trường | Ý nghĩa |
|---|---|
| `ttl` | số giây giữ mở trước khi servo tự về 0°. Mặc định 5 nếu thiếu trường này. |

ESP32: servo → 90°, LED xanh sáng, OLED "ACCESS GRANTED", 1 tiếng bíp ngắn.

**Bị bỏ qua nếu ESP32 đang trong thời gian lockout.**

### 4.2. `deny`

```json
{"action":"deny"}
```

ESP32: LED đỏ nháy 3 lần, 2 tiếng bíp, OLED "ACCESS DENIED". Servo không đổi.

### 4.3. `lockout`

```json
{"action":"lockout","sec":30}
```

| Trường | Ý nghĩa |
|---|---|
| `sec` | số giây khóa. Mặc định 30 nếu thiếu trường này. |

ESP32: OLED đếm ngược, LED đỏ sáng liên tục, servo về 0°, **bỏ qua mọi lệnh `unlock`**
cho tới khi hết giờ.

**Mẹo dùng `sec: 0` để hủy lockout:**

```json
{"action":"lockout","sec":0}
```

Đặt hạn lockout là "ngay bây giờ", nên vòng `loop()` kế tiếp thấy đã quá hạn và tự trả
ESP32 về trạng thái khóa bình thường. Đây là cách nút "RESET LOCKOUT" trên Dashboard xóa
lockout ở phía ESP32 mà không cần thêm action thứ tư ngoài spec.

---

## 5. `.../state` — uplink

**Đầy đủ:** `huit/ak_majespecter/gate/state`
**Publish bởi:** `publishState()` trong `firmware/gate_lock.cpp`
**Subscribe bởi:** node `uplink .../state` trong `middleware/flows.json`

### Payload

```json
{"lock":"closed","attempts":0,"uptime":123}
```

| Trường | Kiểu | Giá trị |
|---|---|---|
| `lock` | string | `"closed"` / `"open"` / `"lockout"` |
| `attempts` | number | số lần bị từ chối liên tiếp, theo góc nhìn của ESP32. Về 0 khi mở khóa thành công hoặc hết lockout. |
| `uptime` | number | số giây từ lúc ESP32 khởi động |

### Ba trạng thái

```json
{"lock":"closed","attempts":0,"uptime":15}
{"lock":"open","attempts":0,"uptime":48}
{"lock":"lockout","attempts":3,"uptime":92}
```

> Ba payload trên là **định dạng firmware sẽ sinh ra** theo code. **Chưa chạy thật**
> trên Wokwi nên chưa có bản ghi thực tế — sẽ bổ sung sau khi test end-to-end.

**Tần suất:** mỗi 5 giây **và** ngay lập tức mỗi khi trạng thái đổi. Node-RED dùng nhịp
5 giây này làm watchdog: quá 15 giây (lỡ 3 nhịp) không nghe gì thì báo "MẤT KẾT NỐI".

---

## 6. Bảng mã cử chỉ

| class_id | Lớp | Mô tả | Hex |
|---|---|---|---|
| 0 | `fist` | nắm tay | `3A` |
| 1 | `palm` | xòe bàn tay | `7C` |
| 2 | `victory` | chữ V | `E1` |
| 3 | `thumb_up` | ngón cái lên | `B9` |
| 4 | `point_up` | chỉ tay lên | `05` |
| 5 | `ok` | vòng tròn OK | `4D` |
| 6 | `none` | không hợp lệ / chuyển tiếp | — (không có mã) |

Lớp `none` **không bao giờ được publish**. Nó chỉ là trạng thái phân cách: sau khi
chấp nhận một cử chỉ, phải qua ít nhất 10 khung `none` mới nhận cử chỉ tiếp theo.
Không có luật này thì giữ yên một bàn tay 45 khung sẽ bị đếm thành 3 cử chỉ giống nhau
và tự sinh ra một mật mã.

**Mật mã mặc định:** `palm → victory → fist` = `7CE13A`

---

## 7. Cách tự kiểm tra topic bằng tay

Cài `mosquitto-clients` rồi nghe toàn bộ:

```bash
mosquitto_sub -h broker.hivemq.com -p 1883 -t "huit/ak_majespecter/gate/#" -v
```

Giả lập Node-RED ra lệnh mở khóa (ESP32 phải quay servo):

```bash
mosquitto_pub -h broker.hivemq.com -p 1883 \
  -t "huit/ak_majespecter/gate/cmd" -m '{"action":"unlock","ttl":5}'
```

Giả lập Python gửi mã đúng (Node-RED phải ra lệnh unlock):

```bash
mosquitto_pub -h broker.hivemq.com -p 1883 \
  -t "huit/ak_majespecter/gate/sequence" -m '{"code":"7CE13A","ts":1789220972}'
```

> **Lưu ý:** đây là broker công cộng. Mọi thứ bạn publish, người khác nghe được; và
> người khác cũng publish vào topic của bạn được. Đừng dùng prefix chung chung như
> `test/gate` — dễ đụng người lạ. Prefix có MSSV chính là để tránh việc này.
