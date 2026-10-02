# AI Hand-Gesture Authenticated Smart Door Lock

**EN:** AI Hand-Gesture Authenticated Smart Door Lock — A Four-Layer IoT System Using
MediaPipe Hand Landmark Classification and MQTT

**VI:** Khóa cửa thông minh xác thực bằng chuỗi cử chỉ tay — Hệ thống IoT bốn tầng
dùng phân loại điểm mốc bàn tay MediaPipe và MQTT

> **TODO — MSSV:** hiện đang dùng prefix tạm `huit/ak_majespecter/gate/`.
> Khi có MSSV thật, sửa **một chỗ duy nhất**: `mqtt.topic_prefix` trong
> [vision/config.json](vision/config.json), rồi sửa cho khớp trong
> [firmware/gate_lock.cpp](firmware/gate_lock.cpp) và
> [middleware/flows.json](middleware/flows.json).

---

## 1. Ý tưởng

Người dùng thực hiện một **chuỗi 3 cử chỉ tay** trước webcam. Mỗi cử chỉ được phân loại
bằng MediaPipe HandLandmarker + một MLP nhỏ, rồi ánh xạ thành 1 byte hex. Ghép 3 byte
lại thành mật mã (mặc định `7CE13A`). Node-RED kiểm mã và ra lệnh mở khóa cho ESP32
(mô phỏng trên Wokwi).

---

## 2. Kiến trúc 4 tầng

```
┌─ Tầng 4 — APPLICATION ──────────────────────────────────────────┐
│  Node-RED Dashboard: trạng thái khóa, log 10 lần gần nhất,      │
│  nút "Mở khẩn cấp", nút "Reset lockout", biểu đồ thành/bại      │
└───────────────────────────▲──────────────────┬──────────────────┘
                            │                  │
┌─ Tầng 3 — MIDDLEWARE ─────┴──────────────────▼──────────────────┐
│  Node-RED: kiểm mã, đếm số lần sai, lockout 30s, ghi           │
│  access_log.csv                                                 │
└───────────────────────────▲──────────────────┬──────────────────┘
                     uplink │                  │ downlink
                            │                  │
┌─ Tầng 2 — NETWORK ────────┴──────────────────▼──────────────────┐
│  MQTT — broker.hivemq.com:1883 (công cộng, không auth)          │
│  uplink  : .../gesture  .../sequence  .../state                 │
│  downlink: .../cmd                                              │
└──────▲──────────────────────────────────────────────▲───────────┘
       │ publish                          subscribe   │ publish
       │                                              │
┌──────┴─────────────────────┐      ┌─────────────────┴───────────┐
│ Tầng 1a — SENSING (laptop) │      │ Tầng 1b — ACTUATING (ESP32) │
│ webcam + MediaPipe + MLP   │      │ servo, OLED, buzzer, 2 LED  │
│ vision/gesture_lock.py     │      │ firmware/gate_lock.cpp      │
└────────────────────────────┘      └─────────────────────────────┘
```

**Vì sao phải tách 2 máy:** script Python trên laptop là một **node cảm biến độc lập**,
không phải một phần của ESP32. Hai thiết bị nói chuyện **hoàn toàn qua MQTT**. Wokwi chạy
trên cloud nên không thấy được `localhost` của máy bạn — bắt buộc dùng broker công cộng.

**Luồng uplink** (thiết bị → hệ thống): `gesture_lock.py` publish `.../sequence`
→ Node-RED nhận và kiểm mã.
**Luồng downlink** (hệ thống → thiết bị): Node-RED publish `.../cmd`
→ ESP32 subscribe và quay servo.
Luồng downlink thứ hai: nút "Mở khẩn cấp" trên Dashboard publish thẳng `.../cmd`.

---

## 3. Bảng MQTT topic

Broker `broker.hivemq.com`, port `1883`, không auth. Prefix: `huit/ak_majespecter/gate/`

| Topic | Hướng | Ai publish → ai subscribe | Payload mẫu |
|---|---|---|---|
| `.../gesture`  | uplink   | Python → Node-RED, ESP32 | `{"gesture":"victory","hex":"E1","conf":0.93,"ts":1699}` |
| `.../sequence` | uplink   | Python → Node-RED        | `{"code":"7CE13A","ts":1699}` |
| `.../cmd`      | downlink | Node-RED → ESP32         | `{"action":"unlock","ttl":5}` / `{"action":"deny"}` / `{"action":"lockout","sec":30}` |
| `.../state`    | uplink   | ESP32 → Node-RED         | `{"lock":"open","attempts":1,"uptime":123}` |

---

## 4. Bảng mã cử chỉ

| class_id | Lớp | Mô tả | Hex |
|---|---|---|---|
| 0 | `fist` | nắm tay | `0x3A` |
| 1 | `palm` | xòe bàn tay | `0x7C` |
| 2 | `victory` | chữ V | `0xE1` |
| 3 | `thumb_up` | ngón cái lên | `0xB9` |
| 4 | `point_up` | chỉ tay lên | `0x05` |
| 5 | `ok` | vòng tròn OK | `0x4D` |
| 6 | `none` | không hợp lệ / chuyển tiếp | — |

Lớp `none` **bắt buộc phải có** — nó là trạng thái phân cách giữa hai cử chỉ, giúp
máy biết bạn đã kết thúc cử chỉ này và chuẩn bị làm cử chỉ tiếp theo.

Mật mã mặc định: `palm → victory → fist` = **`7CE13A`**

---

## 5. Ngưỡng hệ thống

| Tham số | Giá trị |
|---|---|
| Khung giữ ổn định để chấp nhận 1 cử chỉ | 15 |
| Confidence tối thiểu | 0.70 |
| Số khung `none` tối thiểu giữa 2 cử chỉ | 10 |
| Timeout toàn chuỗi | 10 giây |
| Độ dài mã | 3 cử chỉ |
| Số lần sai trước lockout | 3 |
| Thời gian lockout | 30 giây |
| Servo đóng / mở | 0° / 90° |
| Thời gian giữ mở | 5 giây |

Tất cả nằm trong [vision/config.json](vision/config.json).

---

## 6. Cách chạy

Môi trường Python nằm **trong thư mục dự án** (`.conda/`), không cài ở ổ C.
Luôn gọi thẳng `python.exe` của env, không cần `conda activate`:

```powershell
D:\IoT_Gesture_sequence_door_lock\.conda\python.exe --version
```

### 6.1. Thu thập dữ liệu (cần webcam + bạn tự thao tác)

```powershell
D:\IoT_Gesture_sequence_door_lock\.conda\python.exe vision\collect_data.py
```
Phím: `0`–`6` chọn lớp · `SPACE` ghi 1 mẫu · `R` ghi liên tục 30 mẫu · `Q` thoát.
Dữ liệu ghi **append** vào `vision/model/keypoint.csv`.

### 6.2. Huấn luyện

```powershell
D:\IoT_Gesture_sequence_door_lock\.conda\python.exe -m jupyter lab
```
Mở `vision/train_classifier.ipynb`, chạy toàn bộ cell.

### 6.3. Firmware ESP32

Tạo project mới trên [wokwi.com](https://wokwi.com), dán `firmware/gate_lock.cpp` và
`firmware/diagram.json`, cài thư viện trong Library Manager (danh sách ở Phase 2).

### 6.4. Node-RED

Import `middleware/flows.json`. Cần cài `node-red-dashboard`.

### 6.5. Chạy nhận diện + gửi MQTT

```powershell
D:\IoT_Gesture_sequence_door_lock\.conda\python.exe vision\gesture_lock.py
```

---

## 7. Dữ liệu huấn luyện

### 7.1. Dữ liệu tự thu — dùng để HUẤN LUYỆN

Thu bằng `vision/collect_data.py` trên webcam của người làm đồ án.
File: `vision/model/keypoint.csv` — 2.594 mẫu, lần ghi cuối **26/09/2026**.

| class_id | Lớp | Số mẫu |
|---|---|---|
| 0 | `fist` | 358 |
| 1 | `palm` | 398 |
| 2 | `victory` | 420 |
| 3 | `thumb_up` | 377 |
| 4 | `point_up` | 300 |
| 5 | `ok` | 374 |
| 6 | `none` | 367 |
| | **Tổng** | **2.594** |

Chia 80/20 có phân tầng (`random_state=42`) thành tập train và tập validation.
Ma trận nhầm lẫn trên tập validation: [docs/confusion_matrix.png](docs/confusion_matrix.png)

### 7.2. HaGRID — dùng làm TẬP KIỂM THỬ ĐỘC LẬP

> **HaGRID KHÔNG được trộn vào tập huấn luyện.**

Model chỉ học từ dữ liệu tự thu ở mục 7.1. HaGRID trả lời một câu hỏi khác:
*"model có nhận được bàn tay của **người khác**, trong điều kiện chụp khác, hay không?"*

Cờ `USE_HAGRID_FOR_TRAINING` trong `vision/train_classifier.ipynb` **mặc định là `False`**
đúng vì lý do này. Bật lên `True` thì HaGRID không còn là tập kiểm thử độc lập nữa và
con số của `vision/eval_external.py` mất ý nghĩa.

File: `vision/model/keypoint_hagrid.csv` — 2.100 mẫu (300 mỗi lớp × 7 lớp), cùng schema
43 cột với `keypoint.csv`. Metadata truy vết ở `keypoint_hagrid_meta.csv`, báo cáo trích
xuất ở `extract_report.json`.

Quy trình trích landmark: [kaggle/extract_hagrid_landmarks.ipynb](kaggle/extract_hagrid_landmarks.ipynb)
(chạy trên Kaggle, đọc trực tiếp từ `/kaggle/input`).

Ánh xạ lớp HaGRID → lớp của dự án:

| HaGRID | → lớp dự án | | HaGRID | → lớp dự án |
|---|---|---|---|---|
| `fist` | `fist` | | `one` | `point_up` |
| `palm` | `palm` | | `ok` | `ok` |
| `peace` | `victory` | | `no_gesture` | `none` |
| `like` | `thumb_up` | | | |

Bốn lớp bị loại bỏ có chủ ý: `peace_inverted`, `stop_inverted`, `two_up_inverted`
(tay úp ngược, hình dạng khác hẳn) và `stop` (lòng bàn tay khép ngón, dễ lẫn với `palm`).

### 7.3. Nguồn và giấy phép HaGRID

> **HaGRID** — HAnd Gesture Recognition Image Dataset.
> Kapitanov, Kvanchiani, Nagaev, Kraynov, Makhliarchuk.
> Giấy phép: biến thể **Creative Commons BY-SA 4.0**.
> Kho chính thức: https://github.com/hukenovs/hagrid

Giấy phép BY-SA yêu cầu **ghi công tác giả** và **giữ nguyên điều kiện chia sẻ** cho
các tác phẩm phái sinh. Thư mục `vision/model/` chứa landmark trích từ HaGRID, nên nó
là tác phẩm phái sinh và chịu cùng điều kiện giấy phép này.

---

## 8. Nguồn model MediaPipe

`vision/model/hand_landmarker.task` được tải tự động lần chạy đầu từ:

```
https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
```

(trang chính thức: https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker)

Dự án dùng **MediaPipe Tasks API** (`mediapipe.tasks.python.vision.HandLandmarker`),
**không** dùng `mp.solutions.hands` (API cũ, sẽ xung đột).

---

## 9. Cấu trúc thư mục

```
IoT_Gesture_sequence_door_lock\
├── .conda\                   môi trường Python (không commit)
├── firmware\
│   ├── gate_lock.cpp         firmware ESP32
│   └── diagram.json          sơ đồ nối dây Wokwi
├── vision\
│   ├── config.json           TOÀN BỘ tham số hệ thống
│   ├── common.py             tiền xử lý landmark dùng chung
│   ├── collect_data.py       thu dữ liệu huấn luyện
│   ├── train_classifier.ipynb
│   ├── gesture_lock.py       nhận diện + state machine + MQTT
│   └── model\                keypoint.csv, .task, .keras, .tflite
├── middleware\
│   └── flows.json            Node-RED flow + dashboard
├── docs\                     tài liệu kiến trúc, test case
├── demo\                     video demo
├── requirements.txt
└── README.md
```

---

## 10. Tài liệu

| File | Nội dung |
|---|---|
| [docs/VIEC_CAN_LAM.md](docs/VIEC_CAN_LAM.md) | **Đọc file này trước.** 10 việc cần làm theo thứ tự phụ thuộc, mỗi việc kèm kết quả đúng và cách xử lý khi sai |
| [docs/HUONG_DAN_CHAY.md](docs/HUONG_DAN_CHAY.md) | Tài liệu tra cứu: lệnh chạy từng thành phần, bảng phím, ý nghĩa overlay |
| [docs/KIEN_TRUC_4_TANG.md](docs/KIEN_TRUC_4_TANG.md) | Mô tả từng tầng, luồng uplink/downlink cụ thể, vì sao phải tách hai máy |
| [docs/MQTT_TOPICS.md](docs/MQTT_TOPICS.md) | Bảng topic, payload mẫu, lệnh `mosquitto_pub`/`sub` để tự kiểm tra |
| [docs/TEST_CASES.md](docs/TEST_CASES.md) | 18 kịch bản test, cột kết quả để trống cho bạn tự điền |

---

## 11. Môi trường đã kiểm chứng

```
D:\IoT_Gesture_sequence_door_lock\.conda\python.exe
opencv 5.0.0
mediapipe 0.10.31
tf 2.21.0
numpy 2.4.6
```
