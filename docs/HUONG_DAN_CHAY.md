# Hướng dẫn chạy

Làm **đúng thứ tự** từ bước 0 đến bước 6. Mỗi bước có phần "Kiểm tra trước khi đi tiếp" —
đừng bỏ qua, sai ở bước trước sẽ rất khó tìm ra ở bước sau.

**Quy ước:** môi trường Python nằm **trong thư mục dự án** (`.conda/`), không cài ở ổ C.
Mọi lệnh gọi thẳng `python.exe` của môi trường đó, **không cần `conda activate`**.

---

## Bước 0 — Kiểm tra môi trường

```powershell
D:\IoT_Gesture_sequence_door_lock\.conda\python.exe -c "import sys, cv2, mediapipe, paho.mqtt.client, tensorflow as tf; print(sys.executable); print('opencv', cv2.__version__); print('mediapipe', mediapipe.__version__); print('tf', tf.__version__)"
```

Kết quả đúng:

```
D:\IoT_Gesture_sequence_door_lock\.conda\python.exe
opencv 5.0.0
mediapipe 0.10.31
tf 2.21.0
```

**Dòng đầu bắt buộc phải bắt đầu bằng `D:\IoT_Gesture_sequence_door_lock`.**
Nếu nó trỏ vào ổ C thì bạn đang dùng nhầm Python — dừng lại, đừng đi tiếp.

Chạy toàn bộ unit test (không cần webcam, không cần mạng):

```powershell
cd D:\IoT_Gesture_sequence_door_lock\vision
..\.conda\python.exe -m unittest discover -s . -p "test_*.py"
```

Kết quả đúng: `Ran 26 tests ... OK`

### Nếu phải cài lại từ đầu trên máy khác

```powershell
D:\Miniconda3\Scripts\conda.exe create --prefix D:\IoT_Gesture_sequence_door_lock\.conda python=3.11 -y
D:\IoT_Gesture_sequence_door_lock\.conda\python.exe -m pip install -r D:\IoT_Gesture_sequence_door_lock\requirements.txt
```

---

## Bước 1 — Thu dữ liệu huấn luyện

```powershell
cd D:\IoT_Gesture_sequence_door_lock
.\.conda\python.exe vision\collect_data.py
```

Lần chạy đầu sẽ tự tải `hand_landmarker.task` (7.6 MB) về `vision/model/`.

### Phím điều khiển

| Phím | Tác dụng |
|---|---|
| `0`–`6` | chọn lớp cần thu |
| `SPACE` | ghi 1 mẫu |
| `R` | ghi liên tục 30 mẫu, cách nhau 2 khung |
| `Q` hoặc `ESC` | thoát và in bảng đếm |

### Bảng lớp

| Phím | Lớp | Mô tả |
|---|---|---|
| `0` | `fist` | nắm tay |
| `1` | `palm` | xòe bàn tay |
| `2` | `victory` | chữ V |
| `3` | `thumb_up` | ngón cái lên |
| `4` | `point_up` | chỉ tay lên |
| `5` | `ok` | vòng tròn OK |
| `6` | `none` | **không có tay / tay ở tư thế linh tinh** |

### Mục tiêu: 250–300 mẫu mỗi lớp, kể cả `none`

Cách làm nhanh: chọn lớp, làm cử chỉ, bấm `R` khoảng 9–10 lần, **mỗi lần đổi góc tay
một chút** — xoay cổ tay, đưa gần/xa camera, dịch sang trái/phải khung hình.

**Lớp `none` thu thế nào:** thu cả lúc **không có tay** trong khung hình, cả lúc tay
đang **chuyển giữa hai cử chỉ**, cả các tư thế linh tinh không thuộc 6 lớp kia. Đây là
lớp quan trọng nhất và cũng là lớp hay bị thu qua loa nhất.

### ⚠️ Cảnh báo lớn nhất của cả dự án

**Thu dữ liệu tại đúng chỗ và đúng ánh sáng mà bạn sẽ demo.**

Model học cả nền phía sau và điều kiện ánh sáng, không chỉ học hình dạng bàn tay. Thu ở
phòng trọ buổi tối rồi demo ở phòng học buổi sáng là nguyên nhân trượt phổ biến nhất.
Nếu chưa biết sẽ demo ở đâu, hãy thu ở **hai ba chỗ khác nhau** cho model bớt phụ thuộc
vào nền.

### Kiểm tra trước khi đi tiếp

Khi thoát, script in bảng đếm. File dữ liệu:

```powershell
D:\IoT_Gesture_sequence_door_lock\vision\model\keypoint.csv
```

Chạy lại `collect_data.py` nhiều lần được — dữ liệu **ghi thêm vào cuối**, không bao giờ
ghi đè.

---

## Bước 2 — Huấn luyện model

```powershell
cd D:\IoT_Gesture_sequence_door_lock
.\.conda\python.exe -m jupyter lab
```

Mở `vision/train_classifier.ipynb`, chạy toàn bộ cell từ trên xuống
(**Run → Run All Cells**).

### Kiểm tra trước khi đi tiếp

1. Ô đối chiếu TFLite in `Ty le TFLite trung khop voi Keras: 100.0000%`.
   Nếu dưới 99.9% thì **đừng dùng file `.tflite` đó**, kiểm tra lại bước chuyển đổi.
2. **Cell cuối cùng** in độ chính xác từng lớp. Nếu có dòng `CANH BAO`, đọc kỹ:
   - Thu thêm 100–150 mẫu cho **cả hai** lớp trong cặp bị nhầm rồi train lại, **hoặc**
   - Đổi mật mã sang cặp cử chỉ khác (cách này nhanh và chắc hơn) — sửa
     `secret.default_code` trong `vision/config.json` **và** `MA_MAC_DINH` trong
     `middleware/flows.json`.
3. Hai file phải xuất hiện:
   - `vision/model/gesture_classifier.keras`
   - `vision/model/gesture_classifier.tflite` ← file này `gesture_lock.py` mới dùng
4. Hình ma trận nhầm lẫn lưu ở `docs/confusion_matrix.png` (dùng cho báo cáo).

---

## Bước 3 — Nạp firmware lên Wokwi

1. Vào [wokwi.com](https://wokwi.com), tạo project mới **ESP32**.
2. Mở tab **Library Manager**, thêm đúng 6 thư viện (danh sách ở `firmware/libraries.txt`):

   ```
   PubSubClient
   ArduinoJson
   ESP32Servo
   Adafruit SSD1306
   Adafruit GFX Library
   Adafruit BusIO
   ```

   `WiFi.h` và `Wire.h` có sẵn trong ESP32 core, **không** cần thêm.
3. Dán nội dung `firmware/gate_lock.ino` vào tab `sketch.ino`.
4. Dán nội dung `firmware/diagram.json` vào tab `diagram.json`.
5. Bấm **▶ Start**.

### Kiểm tra trước khi đi tiếp

OLED phải hiện:

```
WiFi:OK  MQTT:OK
READY - show code
LOCKED
CODE __ __ __
So lan sai: 0
```

### Xử lý sự cố

| Hiện tượng | Nguyên nhân và cách sửa |
|---|---|
| Wokwi báo đỏ ở một dây trong `diagram.json` | Tên chân GND không khớp. Đổi `esp:GND.2` hoặc `esp:GND.3` thành `esp:GND.1` — mọi GND nối chung, không ảnh hưởng gì. |
| `WiFi:--` mãi không lên `OK` | Kiểm tra SSID đúng là `Wokwi-GUEST`, mật khẩu **rỗng**, channel `6`. |
| `MQTT:--` trong khi `WiFi:OK` | Broker công cộng đôi lúc quá tải. Đợi 30 giây; firmware tự thử lại mỗi 3 giây. |
| Servo giật hoặc buzzer câm | Xung đột bộ đếm LEDC giữa `ESP32Servo` và `tone()`. Báo lại để đổi sang `ledcWriteTone` với kênh cố định. |

---

## Bước 4 — Import flow vào Node-RED

1. Cài Node-RED (nếu chưa có):

   ```powershell
   npm install -g --unsafe-perm node-red
   ```

2. Chạy:

   ```powershell
   node-red
   ```

3. Mở `http://localhost:1880`
4. Cài dashboard: **☰ → Manage palette → Install →** tìm `node-red-dashboard` → Install.
   Đây là gói **duy nhất** phải cài thêm.
5. **☰ → Import →** dán toàn bộ nội dung `middleware/flows.json` → **Import** → **Deploy**.
6. **Sửa đường dẫn file log** nếu dự án không nằm ở `D:\IoT_Gesture_sequence_door_lock`:
   mở node `access_log.csv` (màu vàng nhạt), sửa ô **Filename** thành đường dẫn đúng.
   Node-RED giải đường dẫn tương đối theo `~/.node-red` chứ **không** theo thư mục dự án,
   nên phải để đường dẫn tuyệt đối.
7. Mở dashboard: `http://localhost:1880/ui`

### Kiểm tra trước khi đi tiếp

- Ô "ESP32" trên dashboard hiện `ONLINE (nghe Ns truoc)` trong vòng 15 giây.
- Ô trạng thái ổ khóa hiện `DA KHOA` màu đỏ.
- Bấm nút **"MỞ KHẨN CẤP"** → servo trên Wokwi phải quay. Nếu quay được thì luồng
  downlink đã thông, chưa cần đụng đến camera.

---

## Bước 5 — Chạy nhận diện và thử end-to-end

```powershell
cd D:\IoT_Gesture_sequence_door_lock
.\.conda\python.exe vision\gesture_lock.py
```

### Phím điều khiển

| Phím | Tác dụng |
|---|---|
| `Q` hoặc `ESC` | thoát |
| `R` | xóa chuỗi đang nhập, làm lại từ đầu |

### Đọc overlay

| Vùng trên màn hình | Ý nghĩa |
|---|---|
| Góc trên trái, chữ to | tên lớp + độ tin cậy. Xanh = đạt ngưỡng 0.70, xám = chưa đạt |
| Thanh xanh + `n/15` | đang giữ được bao nhiêu khung. Đủ 15 thì chốt cử chỉ |
| Thanh cam + `HA TAY XUONG` | vừa chốt xong 1 cử chỉ, phải hạ tay đủ 10 khung mới nhận cử chỉ tiếp |
| `MA: E1 7C __` | chuỗi hex đang nhập |
| Góc trên phải, `con 7.3s` | đếm ngược timeout. Đỏ khi dưới 3 giây |
| Góc dưới phải, `MQTT ON (5)` | trạng thái kết nối và số bản tin đã gửi |

### Thao tác chuẩn cho một lần mở khóa

```
1. Làm cử chỉ victory, GIỮ YÊN tới khi thanh xanh đầy      (~0.5 giây)
2. HẠ TAY xuống tới khi thanh cam đầy                       (~0.3 giây)
3. Làm cử chỉ palm, giữ yên
4. Hạ tay
5. Làm cử chỉ ok, giữ yên
-> servo trên Wokwi quay, LED xanh sáng, OLED "ACCESS GRANTED"
```

Điểm hay sai: **phải giữ yên tay, không lướt qua**. Một khung tụt dưới 0.70 là thanh
tiến trình đếm lại từ đầu.

---

## Bước 6 — Điền test case và quay demo

1. Mở `docs/TEST_CASES.md`, chạy đủ 18 kịch bản, điền cột "Kết quả thực tế".
2. Quay video demo. Bố cục nên có **cả ba cửa sổ cùng lúc** trên màn hình:
   - cửa sổ webcam có overlay
   - Wokwi (servo + OLED)
   - dashboard Node-RED

   Ba cửa sổ cùng khung hình là cách chứng minh 4 tầng hoạt động thật, rõ hơn mọi lời giải thích.
3. Nội dung video nên có, theo thứ tự:
   - Mở khóa thành công (TC-01)
   - Nhập sai 3 lần → lockout (TC-03)
   - Làm **chuỗi đúng** trong lúc lockout → vẫn bị chặn (TC-04) ← **cảnh ấn tượng nhất**
   - Bấm Reset lockout rồi mở khẩn cấp từ dashboard (TC-15, TC-13)
4. Lưu video vào `demo/` (thư mục này đã được `.gitignore` bỏ qua file `.mp4`).

---

## Phụ lục — Lệnh hay dùng

**Nghe toàn bộ topic:**
```bash
mosquitto_sub -h broker.hivemq.com -p 1883 -t "huit/ak_majespecter/gate/#" -v
```

**Giả lập gửi mã đúng (không cần webcam):**
```bash
mosquitto_pub -h broker.hivemq.com -p 1883 -t "huit/ak_majespecter/gate/sequence" -m '{"code":"E17C4D","ts":1}'
```

**Giả lập mở khóa (không cần Node-RED):**
```bash
mosquitto_pub -h broker.hivemq.com -p 1883 -t "huit/ak_majespecter/gate/cmd" -m '{"action":"unlock","ttl":5}'
```

**Chạy lại toàn bộ unit test:**
```powershell
cd D:\IoT_Gesture_sequence_door_lock\vision
..\.conda\python.exe -m unittest discover -s . -p "test_*.py"
```

**Xem log truy cập:**
```powershell
type D:\IoT_Gesture_sequence_door_lock\middleware\access_log.csv
```
