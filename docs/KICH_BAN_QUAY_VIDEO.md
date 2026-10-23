# Kịch bản quay video demo

Mục tiêu: một video 3–4 phút chứng minh **cả 4 tầng chạy thật**, gồm 5 cảnh bắt buộc. Quay
**một bản hoàn chỉnh dù còn lỗi nhỏ** — demo trực tiếp lúc bảo vệ rất dễ trục trặc, có video
sẵn thì không trắng tay.

---

## 1. Bố trí màn hình

Ba cửa sổ trên **cùng một khung hình**, quay toàn màn hình 1920×1080:

```
┌──────────────────────────────┬──────────────────────────────┐
│                              │                              │
│  ① CỬA SỔ WEBCAM + OVERLAY   │  ② WOKWI                     │
│  vision/gesture_lock.py      │  servo, OLED, 2 LED, buzzer  │
│  (640×480, không thu nhỏ)    │  phóng to sơ đồ mạch cho     │
│                              │  thấy rõ chữ trên OLED       │
│  góc trên trái: tên lớp +    │                              │
│  độ tin cậy; thanh 15 khung; │                              │
│  MA: __ __ __; MQTT ON (n)   │                              │
├──────────────────────────────┼──────────────────────────────┤
│                              │                              │
│  (để trống, hoặc terminal    │  ③ NODE-RED DASHBOARD        │
│  chạy scripts\dem_10_lan.py  │  http://localhost:1880/ui    │
│  — tùy chọn, cho thấy bản    │  trạng thái khóa, ESP32,     │
│  tin MQTT đi qua tầng 2)     │  bảng 10 lần, biểu đồ, 2 nút │
│                              │                              │
└──────────────────────────────┴──────────────────────────────┘
```

- Cửa sổ ① giữ nguyên kích thước 640×480 — thu nhỏ thì chữ overlay không đọc được.
- Wokwi: phóng to (Ctrl + lăn chuột) tới khi đọc được chữ trên OLED trong video.
- Dashboard: thu trình duyệt cho vừa ô, đủ thấy ô trạng thái khóa và bảng lịch sử.
- Âm thanh: **bật tiếng tab Wokwi** — tiếng bíp của buzzer là bằng chứng nghe được cho
  `deny` (2 tiếng) và cho lệnh bị chặn lúc lockout (1 tiếng trầm).

**Phần mềm quay:** OBS Studio, nguồn "Display Capture" (quay cả màn hình). Không dùng Xbox
Game Bar (Win + Alt + R) — nó chỉ quay một cửa sổ ứng dụng, không quay được ba cửa sổ cùng lúc.

---

## 2. Chuẩn bị (5 phút, làm trước khi bấm quay)

1. Khởi động lại Node-RED (Ctrl+C ở cửa sổ đang chạy, rồi chạy lại `node-red`). Context
   lưu trong bộ nhớ nên việc này xóa bảng lịch sử, biểu đồ và bộ đếm sai — Dashboard sạch
   cho cảnh 1.
2. Wokwi: bấm ▶ Start, đợi OLED hiện `WiFi:OK  MQTT:OK`.
3. Chạy tiền kiểm, mọi mục phải PASS:
   `.conda\python.exe scripts\kiem_truoc_khi_demo.py`
4. Chạy `.conda\python.exe vision\gesture_lock.py`, kiểm overlay hiện `MQTT ON`.
5. Ngồi đúng chỗ và đúng ánh sáng đã dùng khi thu dữ liệu. Tập 1 lần chuỗi đúng không
   quay. Nếu lần tập đó mở khóa, đợi servo về 0° rồi mới bắt đầu.
6. Bật OBS, kiểm khung hình có đủ 3 cửa sổ, rồi bấm **Start Recording**.

---

## 3. Năm cảnh bắt buộc — làm đúng thứ tự này

Thứ tự quan trọng: bộ đếm sai phải bắt đầu từ 0 ở cảnh 3, và cảnh 5 phải nằm **ngoài** thời
gian lockout.

### Cảnh 1 — Trạng thái ban đầu (~15 giây)

| Thao tác | Phải thấy trong khung hình |
|---|---|
| Không làm gì, giữ tay ngoài khung. | OLED: `WiFi:OK  MQTT:OK`, `READY - show code`, `LOCKED`, `CODE __ __ __`, `So lan sai: 0`. Dashboard: ô trạng thái ESP32 `DA KHOA`, ô kết nối `ONLINE (nghe …s truoc)`. Overlay: `NONE`, `MA: __ __ __`, `MQTT ON`. |

Lời dẫn gợi ý: *"Hệ thống gồm bốn tầng: laptop nhận diện cử chỉ, broker MQTT, Node-RED kiểm
mã, và ESP32 điều khiển khóa. Hiện khóa đang đóng."*

### Cảnh 2 — Nhập chuỗi đúng, mở khóa (~30 giây)

| Thao tác | Phải thấy |
|---|---|
| Làm `palm`, giữ yên tới khi thanh xanh đầy 15/15. | Overlay `MA: 7C __ __`, OLED `CODE 7C __ __`. |
| Hạ tay khỏi khung tới khi thanh cam (`HA TAY XUONG`) đầy. | — |
| Làm `victory`, giữ yên; hạ tay. | `MA: 7C E1 __`. |
| Làm `fist`, giữ yên. | Servo quay 90°, LED xanh, OLED `ACCESS GRANTED`, 1 tiếng bíp. Dashboard: ô kết quả `MO KHOA`, ô trạng thái ESP32 `DA MO`, bảng lịch sử thêm dòng `DUNG — MO KHOA`, cột "Thành công" của biểu đồ tăng 1. |
| Đợi 5 giây. | Servo tự về 0°, OLED về `LOCKED`. |

Lời dẫn: *"Ba cử chỉ được ghép thành mã 7CE13A, gửi qua MQTT lên Node-RED. Node-RED kiểm
mã đúng và gửi lệnh mở khóa xuống ESP32 — đó là luồng downlink."*

### Cảnh 3 — Nhập chuỗi sai, bị từ chối (~25 giây)

| Thao tác | Phải thấy |
|---|---|
| Làm `thumb_up` → hạ tay → `thumb_up` → hạ tay → `thumb_up` (mã `B9B9B9`). | LED đỏ nháy 3 lần, 2 tiếng bíp, OLED `ACCESS DENIED`. Servo **không** quay. Dashboard: ô kết quả `TU CHOI`, bảng lịch sử thêm dòng `SAI (lan 1/3)`. |

Nếu model đọc nhầm thành cử chỉ khác thì vẫn là một mã sai — cứ để video chạy tiếp.

### Cảnh 4 — Lockout chặn cả mã đúng (~60 giây) — cảnh quan trọng nhất

| Thao tác | Phải thấy |
|---|---|
| Nhập thêm một chuỗi sai (`thumb_up` ×3). | `SAI (lan 2/3)`. |
| Nhập chuỗi sai lần thứ ba. | Node-RED gửi `lockout`: OLED **đếm ngược từ 30**, LED đỏ **sáng liên tục** (không nháy). Dashboard: ô kết quả `LOCKOUT`. |
| **Ngay lập tức** nhập **chuỗi đúng** `palm → victory → fist`. | Servo **không** quay, OLED vẫn đếm ngược, không có tiếng bíp mở khóa. Ô kết quả `BI CHAN`, bảng lịch sử thêm dòng `BI CHAN (dang lockout)`. |
| *(nên có)* Vẫn trong lockout, bấm **MỞ KHẨN CẤP** trên Dashboard. | Servo vẫn **không** quay; buzzer kêu **1 tiếng trầm** — ESP32 cố ý bỏ qua `unlock` khi đang khóa (TC-14). |

Phải làm xong chuỗi đúng trong vòng 30 giây lockout: nhập 3 cử chỉ mất khoảng 5–10 giây,
nên bắt đầu ngay khi thấy OLED đếm ngược. Lời dẫn: *"Sau ba lần sai, hệ thống khóa 30
giây. Kể cả mã đúng cũng bị chặn, và nút mở khẩn cấp cũng bị firmware từ chối."*

### Cảnh 5 — Mở khẩn cấp từ Dashboard (~25 giây)

| Thao tác | Phải thấy |
|---|---|
| Bấm **RESET LOCKOUT** (hoặc đợi hết 30 giây). | LED đỏ tắt, OLED về màn hình chờ. |
| Bấm **MỞ KHẨN CẤP**. | Servo quay 90°, LED xanh. Bảng lịch sử thêm dòng `MO TU DASHBOARD`. Sau 5 giây servo về 0°. |

Lời dẫn: *"Đây là luồng downlink thứ hai: lệnh đi thẳng từ Dashboard xuống ESP32, không qua
khâu nhận diện — dùng khi camera hỏng. Nó chỉ hoạt động ngoài thời gian lockout."*

Kết thúc: dừng 3 giây trên Dashboard để thấy cả bảng lịch sử và biểu đồ, rồi **Stop
Recording**.

---

## 4. Sau khi quay

1. Lưu file vào `demo\`, đặt tên `demo_YYYYMMDD.mp4` (git đã bỏ qua `demo/*.mp4`; nộp riêng).
2. Xem lại một lượt, kiểm đủ 5 cảnh và đọc được chữ trên OLED.
3. Ghi vào `docs/BAO_CAO_KY_THUAT.md` mục 6.2 những gì video cho thấy khác với kết quả
   mong đợi trong `docs/TEST_CASES.md` (TC-01, TC-02, TC-03, TC-04, TC-13, TC-14, TC-15).

## 5. Nếu có trục trặc giữa chừng

| Hiện tượng | Xử lý |
|---|---|
| Một cử chỉ mãi không nhận (thanh xanh tụt liên tục) | Đưa tay gần camera hơn, giữ yên hơn. Không tắt quay — cắt đoạn đó khi dựng nếu cần. |
| Cảnh 4: hết 30 giây trước khi nhập xong chuỗi đúng | Nhập sai 3 lần lại từ đầu để vào lockout mới, rồi làm chuỗi đúng ngay. |
| OLED `MQTT:--` | Wokwi mất kết nối broker: Stop rồi Start lại Wokwi, đợi `MQTT:OK`. |
| Mã đúng mà bị TỪ CHỐI | Node-RED đang giữ mã khác trong context: dừng quay, chạy lại `scripts\kiem_truoc_khi_demo.py` và làm theo hướng dẫn nó in ra. |
