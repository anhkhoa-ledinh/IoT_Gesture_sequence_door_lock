# AI Hand-Gesture Authenticated Smart Door Lock

**EN:** AI Hand-Gesture Authenticated Smart Door Lock — A Four-Layer IoT System Using
MediaPipe Hand Landmark Classification and MQTT

**VI:** Khóa cửa thông minh xác thực bằng chuỗi cử chỉ tay — Hệ thống IoT bốn tầng
dùng phân loại điểm mốc bàn tay MediaPipe và MQTT

Đồ án môn IoT — HUIT, đề tài 9. Nhóm: Lê Đình Anh Khoa (2001230411), Phan Đình Quang (2001230715).

---

## 0. Người mới đọc phần này trước

Bạn đưa tay trước webcam, làm **3 cử chỉ liên tiếp** (mặc định: xòe tay → OK → nắm tay). Nếu
đúng thứ tự, cửa (servo trên ESP32 mô phỏng) mở 5 giây. Sai 3 lần thì khóa 30 giây.

**Chọn đường đọc theo việc bạn cần:**

| Bạn muốn… | Đọc |
|---|---|
| Chạy thử lần đầu trên máy mới | [Mục 3 — Cài đặt](#3-cài-đặt-lần-đầu) rồi [Mục 4 — Chạy](#4-chạy-hệ-thống) |
| Đổi mật mã cử chỉ | [Mục 5](#5-đổi-mật-mã) |
| Quay video để thêm dữ liệu train | [Mục 6](#6-thu-thêm-dữ-liệu-bằng-video-hướng-dẫn-quay) |
| Train lại model | [Mục 7](#7-huấn-luyện-lại-model) |
| Gặp lỗi | [Mục 8 — Lỗi thường gặp](#8-lỗi-thường-gặp) |
| Hiểu kiến trúc để trình bày | [Mục 2](#2-kiến-trúc-4-tầng), [docs/KIEN_TRUC_4_TANG.md](docs/KIEN_TRUC_4_TANG.md) |

**Ba quy ước cần nhớ:**

1. Môi trường Python nằm **trong thư mục dự án** (`.conda\`), không cài ở ổ C. Mọi lệnh gọi
   thẳng `.conda\python.exe`, **không cần** `conda activate`.
2. Mọi tham số (mật mã, ngưỡng, topic MQTT) nằm trong **một file**: `vision/config.json`.
3. Không commit bí mật: `vision/mqtt_tai_khoan.json`, `firmware/secrets.h`,
   `middleware/flows_broker_rieng.json` đã nằm trong `.gitignore`.

---

## 1. Ý tưởng

Người dùng thực hiện một **chuỗi 3 cử chỉ tay** trước webcam. Mỗi cử chỉ được phân loại
bằng MediaPipe HandLandmarker + một MLP nhỏ, rồi ánh xạ thành 1 byte hex. Ghép 3 byte
lại thành mật mã (mặc định `7C4D3A`). Node-RED kiểm mã và ra lệnh mở khóa cho ESP32
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
(Wokwi không có camera, nên camera nằm ở laptop là đúng thiết kế, không phải thiếu sót.)

**Luồng uplink** (thiết bị → hệ thống): `gesture_lock.py` publish `.../sequence`
→ Node-RED nhận và kiểm mã.
**Luồng downlink** (hệ thống → thiết bị): Node-RED publish `.../cmd`
→ ESP32 subscribe và quay servo.
Luồng downlink thứ hai: nút "Mở khẩn cấp" trên Dashboard gửi `.../cmd` (bị chặn khi đang lockout).

---

## 3. Cài đặt lần đầu

### 3.1. Phần mềm cần có

| Phần mềm | Dùng cho | Ghi chú |
|---|---|---|
| [Miniconda](https://docs.conda.io/en/latest/miniconda.html) | tạo môi trường Python 3.11 | chỉ dùng để tạo `.conda\` một lần |
| [Node.js](https://nodejs.org) (bản LTS) | chạy Node-RED | |
| [VS Code](https://code.visualstudio.com) + extension **PlatformIO IDE** + **Wokwi Simulator** | build và mô phỏng ESP32 | hoặc dùng web [wokwi.com](https://wokwi.com), không cần cài gì |
| Webcam | nhận diện cử chỉ | webcam laptop là đủ |

### 3.2. Tạo môi trường Python (một lần, khoảng 10 phút)

```powershell
cd D:\IoT_Gesture_sequence_door_lock
conda create --prefix .\.conda python=3.11 -y
.conda\python.exe -m pip install -r requirements.txt
```

> Nếu lệnh `conda` không có, gọi thẳng đường dẫn, ví dụ `D:\Miniconda3\Scripts\conda.exe create ...`.
> Dự án đặt ở ổ khác thì thay `D:\IoT_Gesture_sequence_door_lock` bằng đường dẫn của bạn.

**Kiểm tra:** chạy toàn bộ test (không cần webcam, không cần mạng):

```powershell
.conda\python.exe -m pytest -q
```

Kết quả đúng: dòng cuối ghi `... passed`, không có `failed`.

### 3.3. Cài Node-RED và nạp flow (một lần)

```powershell
npm install -g --unsafe-perm node-red
cd D:\IoT_Gesture_sequence_door_lock
node-red
```

1. Mở `http://localhost:1880`.
2. **☰ → Manage palette → Install** → tìm `node-red-dashboard` → Install.
3. **☰ → Import** → chọn file `middleware/flows.json` → **Import** → bấm **Deploy** (nút đỏ góc phải).
4. Dự án **không** ở `D:\IoT_Gesture_sequence_door_lock`? Mở node `access_log.csv`, sửa ô
   **Filename** thành đường dẫn tuyệt đối đúng, rồi Deploy.

### 3.4. ESP32 trên Wokwi (chọn một trong hai cách)

**Cách A — web wokwi.com (dễ nhất):**
1. Tạo project mới **ESP32**.
2. Tab **Library Manager**: thêm 6 thư viện trong `firmware/libraries.txt`.
3. Dán `firmware/gate_lock.cpp` vào `sketch.ino`, dán `firmware/diagram.json` vào `diagram.json`.
4. Bấm **▶ Start**.

**Cách B — VS Code (chạy trên máy):**
1. Mở thư mục dự án bằng VS Code, đợi PlatformIO tải xong.
   **Lần đầu rất lâu (10–20 phút)** vì phải tải bộ biên dịch ESP32 — đó là bình thường.
2. Thanh dưới cùng bấm **✓ Build**, đợi `SUCCESS`.
3. **F1 → Wokwi: Request a New License** (lần đầu, miễn phí), rồi **F1 → Wokwi: Select Config File** →
   chọn `firmware/wokwi.toml`.
4. **F1 → Wokwi: Start Simulator**.

**Kiểm tra:** OLED hiện `WiFi:OK MQTT:OK` và `LOCKED`.

---

## 4. Chạy hệ thống

Mỗi lần chạy demo, mở theo thứ tự này:

| # | Việc | Lệnh / thao tác |
|---|---|---|
| 1 | Bật Node-RED | `node-red` (trong thư mục dự án) → dashboard ở `http://localhost:1880/ui` |
| 2 | Bật ESP32 | Wokwi **Start** — đợi `WiFi:OK MQTT:OK` |
| 3 | Thử downlink | bấm **MỞ KHẨN CẤP** trên dashboard → servo phải quay |
| 4 | Tiền kiểm | `.conda\python.exe scripts\kiem_truoc_khi_demo.py` → phải PASS hết |
| 5 | Bật camera | `.conda\python.exe vision\gesture_lock.py` |

**Mở khóa:**

```
1. Làm cử chỉ palm (xòe tay), GIỮ YÊN tới khi thanh xanh đầy
2. HẠ TAY xuống tới khi thanh cam đầy
3. Làm ok, giữ yên → hạ tay
4. Làm fist (nắm tay), giữ yên
→ servo quay, LED xanh sáng, OLED "ACCESS GRANTED"
```

Phím trong cửa sổ camera: `R` xóa chuỗi đang nhập · `Q` / `ESC` thoát.

Giải thích từng vùng trên màn hình camera: [docs/HUONG_DAN_CHAY.md](docs/HUONG_DAN_CHAY.md) bước 5.

---

## 5. Đổi mật mã

Mật mã là 3 mã hex ghép lại, lấy từ [bảng mã cử chỉ](#10-bảng-mã-cử-chỉ). Ví dụ
`victory → palm → ok` = `E1` `7C` `4D` = **`E17C4D`**.

Phải sửa **hai chỗ** cho khớp nhau:

1. `vision/config.json` → `"secret"` → `"default_code": "E17C4D"`
2. `middleware/flows.json` → tìm `MA_MAC_DINH` → `const MA_MAC_DINH = "E17C4D";`

Rồi nạp lại Node-RED: **☰ → Import → `flows.json` → Replace → Deploy**, sau đó **tắt và chạy
lại `node-red`**. Node-RED giữ mã cũ trong bộ nhớ, không khởi động lại thì mã cũ vẫn còn
hiệu lực. Kiểm tra bằng `scripts\kiem_truoc_khi_demo.py`.

**Nên chọn** các cử chỉ model nhận tốt: `palm`, `ok`, `fist`, `victory`. **Tránh** `point_up` và
`thumb_up` (nhận kém hơn hẳn trên người lạ — xem mục 12.2.1).

---

## 6. Thu thêm dữ liệu bằng video (hướng dẫn quay)

Cách nhanh nhất để model nhận tốt **nhiều người**: quay video ngắn bằng điện thoại, script tự cắt
khung hình và gắn nhãn. **Không cần gán nhãn từng khung** — tên thư mục chính là nhãn.

### 6.1. Quay thế nào

**Mỗi video: 1 người · 1 cử chỉ · 1 tay · 5–10 giây.**

- Trong lúc quay, giữ đúng cử chỉ nhưng **thay đổi chậm**: xoay cổ tay nhẹ, đưa tay gần rồi
  xa camera, dịch tay qua lại trong khung.
- Giữa các video, đổi **người**, **chỗ / nền**, **ánh sáng**, **tay trái / tay phải**, **camera**.
- Mỗi cử chỉ **ít nhất 10 video, của ít nhất 3 người**. Dưới 5 video một lớp thì notebook
  không chia đủ 5 fold.
- **Đừng quên lớp `none`**: tay thả lỏng, tay đang chuyển giữa hai cử chỉ, tay nửa nắm nửa mở.
- **Tránh**: đổi cử chỉ giữa chừng, hai bàn tay cùng lúc, tay ra khỏi khung, đưa tay quá nhanh bị nhòe.
- Không cần cắt video: script tự bỏ 0,7 giây đầu và cuối.

### 6.2. Bỏ video vào thư mục

Chạy lần đầu để script tự tạo thư mục:

```powershell
.conda\python.exe scripts\trich_video.py
```

```
data_video\
    fist\  palm\  victory\  thumb_up\  point_up\  ok\  none\
```

Chép video vào đúng thư mục, ví dụ `data_video\palm\quang_phonghoc_tayphai.mp4`.
Định dạng: `.mp4`, `.mov`, `.avi`, `.mkv`, `.m4v`, `.webm`.

> `data_video\` nằm trong `.gitignore`: video nặng và có mặt người, **không** đưa lên GitHub.

### 6.3. Chạy thử rồi ghi thật

```powershell
.conda\python.exe scripts\trich_video.py --chay-thu     # chỉ xem, chưa ghi gì
.conda\python.exe scripts\trich_video.py                # ghi thật vào keypoint.csv
```

- Dòng nào có **`<- NGHI SAI NHAN`**: mở ảnh trong `data_video\_xem_truoc\` xem có bỏ nhầm thư
  mục không. Nhãn đúng mà model vẫn đoán sai thì **giữ lại** — đó là video có giá trị nhất.
- Script **tự sao lưu** `keypoint.csv` trước khi ghi, và nhớ video nào đã trích
  (`data_video\_da_trich.csv`) nên chạy lại chỉ thêm video mới.

Hướng dẫn đầy đủ và giải thích bên trong script: [docs/THU_DU_LIEU_VIDEO.md](docs/THU_DU_LIEU_VIDEO.md).

### 6.4. Cách cũ: thu trực tiếp bằng webcam

```powershell
.conda\python.exe vision\collect_data.py
```

Phím: `0`–`6` chọn lớp · `SPACE` ghi 1 mẫu · `R` ghi liên tục 30 mẫu · `Q` thoát.
Dữ liệu ghi **thêm vào cuối** `vision/model/keypoint.csv`, không ghi đè.

---

## 7. Huấn luyện lại model

```powershell
.conda\python.exe -m jupyter lab
```

1. Mở `vision/train_classifier.ipynb` → **Run → Run All Cells** (khoảng 5–10 phút trên CPU).
2. Ô đối chiếu phải in `Ty le TFLite trung khop voi Keras: 100.0000%`.
3. Notebook ghi đè `vision/model/gesture_classifier.tflite` — `gesture_lock.py` dùng file này
   ngay lần chạy sau, không phải sửa gì thêm.
4. Đo lại trên người lạ (HaGRID): `.conda\python.exe vision\eval_external.py`.

Notebook tự đọc thêm `vision/model/keypoint_github.csv` (dữ liệu công khai, chỉ dùng để train).
Chi tiết từng bước cải tiến: [docs/ket_qua_cai_tien_train.md](docs/ket_qua_cai_tien_train.md).

---

## 8. Lỗi thường gặp

| Hiện tượng | Cách sửa |
|---|---|
| `python` trỏ vào ổ C / thiếu thư viện | Luôn gọi `.conda\python.exe`, không gọi `python` trơn |
| PlatformIO load rất lâu lần đầu | Bình thường — đang tải bộ biên dịch ESP32. Đợi xong một lần, lần sau nhanh |
| `platformio-ide.build not found` | PlatformIO chưa tải xong. Đợi biểu tượng con kiến ở thanh bên trái hiện ra rồi mới Build |
| Wokwi: `firmware binary ... not found` | Chưa Build. Bấm **✓ Build** trước khi Start Simulator |
| OLED `WiFi:--` mãi không lên | SSID phải là `Wokwi-GUEST`, mật khẩu rỗng |
| `MQTT:--` dù `WiFi:OK` | Broker công cộng đôi lúc quá tải. Đợi 30 giây, firmware tự thử lại |
| Buzzer không kêu | Bật tiếng máy / tab trình duyệt, **bấm vào khung mô phỏng một lần** (trình duyệt chặn âm thanh tới khi có thao tác) |
| Dashboard ESP32 `OFFLINE` | Wokwi chưa chạy hoặc chưa kết nối MQTT — xem OLED |
| Làm đúng mã mà không mở | Node-RED còn giữ mã cũ → tắt và chạy lại `node-red`; chạy `scripts\kiem_truoc_khi_demo.py` |
| Phải giữ tay rất lâu mới nhận | Sửa `vision/config.json` → `thresholds.min_confidence` từ `0.8` xuống `0.7` |
| Nhận nhầm cử chỉ ở chỗ mới | Quay thêm video ở chỗ đó (mục 6) rồi train lại (mục 7) |

Thêm cách xử lý từng bước: [docs/HUONG_DAN_CHAY.md](docs/HUONG_DAN_CHAY.md).

---

## 9. Bảng MQTT topic

> **Prefix topic MQTT:** `huit/ak_majespecter/gate/` là **lựa chọn có chủ đích**, không đổi
> sang MSSV: trên broker công cộng, một chuỗi ngẫu nhiên khó đoán hơn MSSV (MSSV có định dạng
> cố định, dễ tra cứu). Prefix chỉ để tránh trùng topic với người khác, **không** phải biện
> pháp bảo mật. Lý do ghi ở `vision/config.json → _ghi_chu_prefix`.

Broker `broker.hivemq.com`, port `1883`, không auth. Prefix: `huit/ak_majespecter/gate/`

| Topic | Hướng | Ai publish → ai subscribe | Payload mẫu |
|---|---|---|---|
| `.../gesture`  | uplink   | Python → Node-RED, ESP32 | `{"gesture":"victory","hex":"E1","conf":0.93,"ts":1699}` |
| `.../sequence` | uplink   | Python → Node-RED        | `{"code":"7C4D3A","ts":1699}` |
| `.../cmd`      | downlink | Node-RED → ESP32         | `{"action":"unlock","ttl":5}` / `{"action":"deny"}` / `{"action":"lockout","sec":30}` |
| `.../state`    | uplink   | ESP32 → Node-RED         | `{"lock":"open","attempts":1,"uptime":123}` |

### 9.1. Broker riêng (tuỳ chọn): TLS + tài khoản + phân quyền

Mặc định dùng broker công cộng ở trên — **ai biết topic cũng gửi được lệnh mở cửa**. Bật
`"dung_broker_rieng": true` trong `vision/config.json` để chuyển sang EMQX Serverless: TLS cổng
8883, mỗi chương trình một tài khoản, chỉ Node-RED được gửi `.../cmd`. Cài đặt khoảng 20 phút:
[docs/BROKER_RIENG_TLS.md](docs/BROKER_RIENG_TLS.md).

---

## 10. Bảng mã cử chỉ

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

Mật mã mặc định: `palm → ok → fist` = **`7C4D3A`** (đổi ngày 31/10 từ `7CE13A` — lý do ở
[docs/ket_qua_cai_tien_train.md](docs/ket_qua_cai_tien_train.md) mục 5).

---

## 11. Ngưỡng hệ thống

| Tham số | Giá trị |
|---|---|
| Khung giữ ổn định để chấp nhận 1 cử chỉ | 15 |
| Confidence tối thiểu | 0.80 (chọn bằng giả lập máy trạng thái, xem mục 12) |
| Số khung `none` tối thiểu giữa 2 cử chỉ | 10 |
| Timeout toàn chuỗi | 10 giây |
| Độ dài mã | 3 cử chỉ |
| Số lần sai trước lockout | 3 |
| Thời gian lockout | 30 giây |
| Servo đóng / mở | 0° / 90° |
| Thời gian giữ mở | 5 giây |

Tất cả nằm trong [vision/config.json](vision/config.json).

---

## 12. Dữ liệu huấn luyện

### 12.1. Dữ liệu tự thu — dùng để HUẤN LUYỆN và ĐÁNH GIÁ

Thu bằng `vision/collect_data.py` trên webcam của người làm đồ án.
File: `vision/model/keypoint.csv` — **2 504 mẫu, 86 burst** (sau khi bỏ 3 burst `none` dán
nhãn sai ngày 23/10; bản gốc 2 594 mẫu giữ ở `keypoint_backup_20261023.csv`).

| class_id | Lớp | Số mẫu | Số burst |
|---|---|---|---|
| 0 | `fist` | 358 | 12 |
| 1 | `palm` | 398 | 14 |
| 2 | `victory` | 420 | 14 |
| 3 | `thumb_up` | 377 | 13 |
| 4 | `point_up` | 300 | 10 |
| 5 | `ok` | 374 | 13 |
| 6 | `none` | 277 | 10 |
| | **Tổng** | **2 504** | **86** |

Đánh giá bằng kiểm định chéo **5 fold chia theo burst** (`StratifiedGroupKFold`, nhóm =
`burst_id` trong `keypoint_meta.csv`) — không burst nào nằm ở cả train lẫn validation. Cách
chia ngẫu nhiên từng mẫu trước đây (83.8%) bị rò rỉ và **không còn dùng**.

**Kết quả (model 31/10):** độ chính xác out-of-fold **76.6%** (trung bình fold 76.5% ± 4.3),
ma trận nhầm lẫn [docs/confusion_matrix.png](docs/confusion_matrix.png), số liệu đầy đủ
`vision/model/eval_metrics.json`. Bảng từng bước cải tiến:
[docs/ket_qua_cai_tien_train.md](docs/ket_qua_cai_tien_train.md).

### 12.1b. Dữ liệu công khai trên GitHub — CHỈ dùng để HUẤN LUYỆN

File: `vision/model/keypoint_github.csv` — **15 620 mẫu**, 6 lớp cử chỉ (không có `none`),
tạo bởi `scripts/chuyen_du_lieu_github.py` từ hai bộ landmark công khai, cùng pipeline
MediaPipe 21 điểm như dự án:

| Nguồn | Giấy phép | Số mẫu |
|---|---|---|
| [thatsabhishek/hand-gesture-recognition-using-mediapipe](https://github.com/thatsabhishek/hand-gesture-recognition-using-mediapipe) — gồm dữ liệu gốc của [Kazuhito00](https://github.com/Kazuhito00/hand-gesture-recognition-using-mediapipe) và [kinivi](https://github.com/kinivi/hand-gesture-recognition-mediapipe) | Apache-2.0 | 5 275 |
| [jaeeun/hand-gesture-recognition-using-mediapipe](https://github.com/jaeeun/hand-gesture-recognition-using-mediapipe) | Apache-2.0 | 10 345 |

Hai bộ này lấy toạ độ pixel; script đổi sang toạ độ chuẩn hoá của camera 640×480 (nhân x với
0.75 rồi chuẩn hoá lại). Trong notebook, dữ liệu GitHub **chỉ được nối vào phần train** của
mỗi fold, với trọng số 0.5 — con số đánh giá vẫn đo trên burst tự thu chưa thấy. Nhờ đó
HaGRID **vẫn là tập kiểm thử độc lập**.

### 12.2. HaGRID — dùng làm TẬP KIỂM THỬ ĐỘC LẬP

> **HaGRID KHÔNG được trộn vào tập huấn luyện.**

Model học từ dữ liệu tự thu (12.1) và dữ liệu GitHub (12.1b), **không** học từ HaGRID. HaGRID trả lời một câu hỏi khác:
*"model có nhận được bàn tay của **người khác**, trong điều kiện chụp khác, hay không?"*

Cờ `USE_HAGRID_FOR_TRAINING` trong `vision/train_classifier.ipynb` **mặc định là `False`**
đúng vì lý do này. Bật lên `True` thì HaGRID không còn là tập kiểm thử độc lập nữa và
con số của `vision/eval_external.py` mất ý nghĩa.

File: `vision/model/keypoint_hagrid.csv` — 2.100 mẫu (300 mỗi lớp × 7 lớp), cùng schema
43 cột với `keypoint.csv`. Metadata truy vết ở `keypoint_hagrid_meta.csv`, báo cáo trích
xuất ở `extract_report.json`.

### 12.2.1. Kết quả đánh giá trên HaGRID

Chạy bằng `vision/eval_external.py`. Ma trận nhầm lẫn:
[docs/confusion_matrix_hagrid.png](docs/confusion_matrix_hagrid.png)

#### Kết quả — model 31/10 so với model 26/09

| Phạm vi | Số mẫu | Model 26/09 | **Model 31/10** |
|---|---|---|---|
| Cả 7 lớp — **con số thô** | 2 100 | 53.8% | **72.7%** |
| 6 cử chỉ (bỏ `none`, xem dưới) | 1 800 | 62.2% | **84.7%** |
| 3 cử chỉ trong mật mã hiện tại (`palm`, `ok`, `fist`) | 900 | — | **96.2%** |

| Lớp | Recall 26/09 | **Recall 31/10** | Precision 31/10 |
|---|---|---|---|
| `fist` | 94.7% | **95.0%** | 72.7% |
| `palm` | 98.0% | **99.7%** | 49.3% |
| `victory` | 51.0% | **94.3%** | 69.4% |
| `thumb_up` | 7.7% | **70.0%** | 98.1% |
| `point_up` | 71.0% | 55.3% | 94.3% |
| `ok` | 51.0% | **94.0%** | 98.9% |
| `none` | **N/A** | **N/A** | — |

Precision của `palm` và `fist` thấp vì `no_gesture` của HaGRID (tay thả lỏng, không có
trong định nghĩa `none` của dự án) dồn vào hai lớp này.

**Khoảng cách generalization:** tự thu 76.6% (7 lớp, out-of-fold) so với HaGRID 72.7% (7 lớp,
con số thô) — cùng phạm vi lớp, cách nhau 3.9 điểm. Phép so cũ "83.8% so với 81.2%, cách 2.6
điểm" sai hai lần (con số tự thu bị rò rỉ, hai bên khác phạm vi lớp) và đã bỏ.

**Lớp `none` — N/A, không phải điểm thấp.** Hai bên định nghĩa khác nhau nên không có
cơ sở so sánh:

- HaGRID `no_gesture`: **có bàn tay** trong khung, chỉ là không làm cử chỉ nào trong
  danh sách.
- Lớp `none` tự thu: gồm cả **tay đang chuyển động giữa hai cử chỉ**, và cả lúc **không
  có tay** trong khung hình.

Lớp `none` tự thu được thiết kế làm **dấu phân cách** giữa hai cử chỉ, còn `no_gesture`
của HaGRID là một tư thế tay tĩnh. Đo lớp này trên HaGRID là đo sai thứ, nên bảng ghi
**N/A** thay vì một con số.

**Lớp `thumb_up` 7.7% ở model 26/09 — chủ yếu do độ phân giải.** Ảnh HaGRID chụp người đứng xa
tới 4 mét: `bbox_area_frac` trung vị chỉ **1.58%** diện tích khung hình (nhỏ nhất
0.115%). Ở kích thước đó **ngón cái không phân giải nổi**, nên `like` của HaGRID trông
y như một bàn tay nắm. Cặp `thumb_up → fist` vốn đã có trên dữ liệu local, ở đây nó bung
lên 76%. Model 31/10 (có thêm dữ liệu GitHub) kéo `thumb_up` lên 70.0%.

#### Tỉ lệ MediaPipe phát hiện được bàn tay

| Lớp HaGRID | → lớp dự án | Tỉ lệ phát hiện |
|---|---|---|
| `palm` | `palm` | 88.0% |
| `ok` | `ok` | 82.2% |
| `one` | `point_up` | 80.2% |
| `peace` | `victory` | 78.3% |
| `like` | `thumb_up` | 60.5% |
| `no_gesture` | `none` | **51.2%** |
| `fist` | `fist` | **50.4%** |

Hai lớp thấp nhất là `fist` (50.4%) và `no_gesture` (51.2%). Nguyên nhân: bộ dò bàn tay
của MediaPipe **dựa nhiều vào hình dạng các ngón duỗi** để định vị bàn tay, mà đúng hai
lớp này **không có ngón nào xòe ra**. Cộng thêm bàn tay rất nhỏ trong khung (1.58% diện
tích), MediaPipe bỏ sót khoảng một nửa số ảnh. Đây là giới hạn của khâu dò bàn tay, xảy
ra **trước** khi model phân loại được gọi.

### 12.2.2. Về tỉ lệ khớp handedness 14.48% — không phải lỗi dữ liệu

`extract_report.json` ghi `handedness.ty_le_khop = 0.1448`. Con số này **không phải cảnh
báo chất lượng dữ liệu** và **không có ngưỡng chặn lọc**. Giải thích đầy đủ:

**Vì sao tỉ lệ thấp.** MediaPipe xác định `handedness` với **giả định ảnh đầu vào là ảnh
gương (selfie)** — đây là quy ước trong tài liệu chính thức của MediaPipe Hands. Pipeline
local có `cv2.flip` trên khung webcam nên thoả giả định đó. Ảnh HaGRID là ảnh chụp bình
thường, notebook lật thêm một lần nữa trước khi đưa vào MediaPipe, nên nhãn trả về
**ngược** tay thật.

Bảng đối chiếu xác nhận đây là **đảo dấu hệ thống**, không phải nhiễu:

| | `leading_hand` = left | `leading_hand` = right |
|---|---|---|
| MediaPipe báo `Left` | 146 | **998** |
| MediaPipe báo `Right` | **798** | 158 |

85.52% ngược, 14.48% khớp. Nếu hai bên đo hai đại lượng không liên quan thì tỉ lệ phải
quanh 50%.

**Vì sao dữ liệu vẫn đúng.** Lật ảnh đổi dấu trục x **và** đổi nhãn handedness. Bước 2
của `preprocess_landmarks` thấy nhãn `Left` nên đổi dấu x **một lần nữa** — hai phép
triệt tiêu nhau. Đã đo trực tiếp: lệch tối đa `2.98e-07` trên 500 bàn tay ngẫu nhiên,
đúng bằng mức làm tròn của `float32`.

**Kết luận:** 42 cột toạ độ trong `keypoint_hagrid.csv` **đúng** và so sánh được với dữ
liệu local. Chỉ cột `mp_handedness` trong `keypoint_hagrid_meta.csv` là không đáng tin —
và không model nào đọc cột đó.

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

### 12.3. Nguồn và giấy phép HaGRID

> **HaGRID** — HAnd Gesture Recognition Image Dataset.
> Kapitanov, Kvanchiani, Nagaev, Kraynov, Makhliarchuk.
> Giấy phép: biến thể **Creative Commons BY-SA 4.0**.
> Kho chính thức: https://github.com/hukenovs/hagrid

Giấy phép BY-SA yêu cầu **ghi công tác giả** và **giữ nguyên điều kiện chia sẻ** cho
các tác phẩm phái sinh. Thư mục `vision/model/` chứa landmark trích từ HaGRID, nên nó
là tác phẩm phái sinh và chịu cùng điều kiện giấy phép này.

---

## 13. Nguồn model MediaPipe

`vision/model/hand_landmarker.task` được tải tự động lần chạy đầu từ:

```
https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
```

(trang chính thức: https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker)

Dự án dùng **MediaPipe Tasks API** (`mediapipe.tasks.python.vision.HandLandmarker`),
**không** dùng `mp.solutions.hands` (API cũ, sẽ xung đột).

---

## 14. Cấu trúc thư mục

```
IoT_Gesture_sequence_door_lock\
├── .conda\                   môi trường Python (không commit)
├── firmware\
│   ├── gate_lock.cpp         firmware ESP32
│   ├── diagram.json          sơ đồ nối dây Wokwi
│   ├── wokwi.toml            cấu hình extension Wokwi trong VS Code
│   └── ca_cert.h             chứng chỉ CA cho broker riêng (TLS)
├── vision\
│   ├── config.json           TOÀN BỘ tham số hệ thống
│   ├── common.py             tiền xử lý landmark dùng chung
│   ├── collect_data.py       thu dữ liệu bằng webcam
│   ├── train_classifier.ipynb
│   ├── eval_external.py      đo model trên HaGRID (người lạ)
│   ├── gesture_lock.py       nhận diện + state machine + MQTT
│   └── model\                keypoint.csv (tự thu), keypoint_github.csv (train),
│                             keypoint_hagrid.csv (chỉ kiểm thử), .task, .keras, .tflite
├── middleware\
│   ├── flows.json            Node-RED flow + dashboard
│   └── certs\                CA bundle cho broker riêng
├── scripts\
│   ├── trich_video.py        video → dữ liệu train (mục 6)
│   ├── kiem_truoc_khi_demo.py   tiền kiểm trước khi demo
│   ├── dem_10_lan.py         đo 10 lần mở khóa
│   ├── doc_access_log.py     đọc log truy cập
│   ├── chuyen_du_lieu_github.py  gom dữ liệu công khai từ GitHub
│   ├── tao_tai_khoan_mqtt.py, kiem_tra_phan_quyen.py   broker riêng
│   └── chan_doan_du_lieu.py  chẩn đoán dữ liệu
├── tests\                    pytest + kiem_thu_flow_node.js (logic Node-RED)
├── kaggle\                   notebook trích landmark HaGRID trên Kaggle
├── docs\                     tài liệu kiến trúc, hướng dẫn, test case, báo cáo
├── data_video\               video quay để lấy dữ liệu (không commit, tự tạo)
├── demo\                     video demo (không commit .mp4)
├── platformio.ini            build firmware bằng PlatformIO
├── requirements.txt
└── README.md
```

---

## 15. Tài liệu

| File | Nội dung |
|---|---|
| [docs/HUONG_DAN_CHAY.md](docs/HUONG_DAN_CHAY.md) | Tra cứu: lệnh chạy từng thành phần, bảng phím, ý nghĩa overlay, xử lý sự cố |
| [docs/VIEC_CON_LAI.md](docs/VIEC_CON_LAI.md) | Những việc còn phải làm trên máy (cần camera, Wokwi, Node-RED) |
| [docs/THU_DU_LIEU_VIDEO.md](docs/THU_DU_LIEU_VIDEO.md) | Quay video để thêm dữ liệu train — cách quay, lệnh chạy, script làm gì bên trong |
| [docs/KICH_BAN_QUAY_VIDEO.md](docs/KICH_BAN_QUAY_VIDEO.md) | Kịch bản quay **video demo** nộp bài (bố cục màn hình, 5 cảnh bắt buộc) |
| [docs/KIEN_TRUC_4_TANG.md](docs/KIEN_TRUC_4_TANG.md) | Mô tả từng tầng, luồng uplink/downlink cụ thể, vì sao phải tách hai máy |
| [docs/MQTT_TOPICS.md](docs/MQTT_TOPICS.md) | Bảng topic, payload mẫu, lệnh `mosquitto_pub`/`sub` để tự kiểm tra |
| [docs/TEST_CASES.md](docs/TEST_CASES.md) | 18 kịch bản test; mục cuối có kết quả kiểm thử tự động ngày 31/10 |
| [docs/BROKER_RIENG_TLS.md](docs/BROKER_RIENG_TLS.md) | Chuyển sang broker riêng: TLS, tài khoản, bảng phân quyền, cách kiểm tra |
| [docs/ket_qua_cai_tien_train.md](docs/ket_qua_cai_tien_train.md) | Từng bước cải tiến huấn luyện, số trước/sau, lý do giữ/bỏ, chọn ngưỡng và mật mã |
| [docs/BAO_CAO_KY_THUAT.md](docs/BAO_CAO_KY_THUAT.md) | Báo cáo kỹ thuật đầy đủ: kiến trúc, kết quả, hạn chế, nguồn từng con số |
| [docs/VIEC_CAN_LAM.md](docs/VIEC_CAN_LAM.md) | Danh sách việc ban đầu (25/09) — đã cũ, giữ để tham khảo |

---

## 16. Môi trường đã kiểm chứng

```
D:\IoT_Gesture_sequence_door_lock\.conda\python.exe   (Python 3.11)
opencv 5.0.0
mediapipe 0.10.31
tf 2.21.0
numpy 2.4.6
PlatformIO: espressif32@7.1.3 (Arduino core 2.0.17)
```
