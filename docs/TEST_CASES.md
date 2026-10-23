# Bảng test case

**Cách dùng:** chạy từng kịch bản theo thứ tự, điền cột **Kết quả thực tế** và
**Đạt/Không**. Cột kết quả thực tế đang để trống — đó là phần bạn phải tự làm và
tự ghi, không được điền sẵn.

**Điều kiện trước khi test:**

- [ ] Đã thu 250–300 mẫu mỗi lớp, `vision/model/keypoint.csv` tồn tại
- [ ] Đã chạy `train_classifier.ipynb`, có `gesture_classifier.tflite`
- [ ] Wokwi đang chạy, OLED hiện `WiFi:OK  MQTT:OK`
- [ ] Node-RED đã import `flows.json` và Deploy, dashboard mở ở `http://localhost:1880/ui`
- [ ] `gesture_lock.py` đang chạy, overlay hiện `MQTT ON`

**Ghi chú khi test:** mở sẵn một cửa sổ nghe toàn bộ topic để đối chiếu:
```bash
mosquitto_sub -h broker.hivemq.com -p 1883 -t "huit/ak_majespecter/gate/#" -v
```

---

## A. Nhóm chức năng chính

| Mã | Kịch bản | Đầu vào | Kết quả mong đợi | Kết quả thực tế | Đạt / Không |
|---|---|---|---|---|---|
| **TC-01** | Chuỗi đúng → mở khóa | Làm `palm` → hạ tay → `victory` → hạ tay → `fist`. Mỗi cử chỉ giữ yên ~1 giây. | Python publish `{"code":"7CE13A",...}`. Node-RED publish `{"action":"unlock","ttl":5}`. Servo quay 90°, LED xanh sáng, OLED "ACCESS GRANTED", 1 tiếng bíp. Sau 5 giây servo tự về 0°. Dashboard hiện "ĐÃ MỞ" màu xanh. Bảng lịch sử thêm 1 dòng "DUNG — MO KHOA". | | |
| **TC-02** | Chuỗi sai → từ chối | Làm `thumb_up` → `thumb_up` → `thumb_up` (mã `B9B9B9`) | Node-RED publish `{"action":"deny"}`. LED đỏ nháy 3 lần, 2 tiếng bíp, OLED "ACCESS DENIED". Servo **không** quay. Dashboard hiện "TỪ CHỐI", ghi "SAI (lan 1/3)". | | |
| **TC-03** | Sai 3 lần liên tiếp → lockout | Lặp lại TC-02 ba lần liên tiếp, không xen kẽ lần đúng nào | Lần 1 và 2: `deny`. **Lần 3**: Node-RED publish `{"action":"lockout","sec":30}`. OLED đếm ngược từ 30, LED đỏ **sáng liên tục** (không nháy). Dashboard hiện "LOCKOUT". | | |
| **TC-04** | Thao tác trong lúc lockout | Ngay sau TC-03, làm **chuỗi ĐÚNG** `palm → victory → fist` | Node-RED **không gửi lệnh nào**. Servo không quay. OLED vẫn đếm ngược. Log ghi "BI CHAN (dang lockout)". Đây là điểm mấu chốt: **mã đúng cũng bị chặn**. | | |
| **TC-05** | Hết lockout → dùng lại bình thường | Đợi hết 30 giây rồi làm chuỗi đúng | LED đỏ tắt, OLED về màn hình chờ, bộ đếm sai về 0. Chuỗi đúng mở được khóa như TC-01. | | |

---

## B. Nhóm state machine phía Python

| Mã | Kịch bản | Đầu vào | Kết quả mong đợi | Kết quả thực tế | Đạt / Không |
|---|---|---|---|---|---|
| **TC-06** | Timeout giữa chừng | Làm `palm`, hạ tay, làm `victory`, rồi **bỏ đi hơn 10 giây** | Overlay đếm ngược từ 10.0s. Khi về 0: chuỗi `7C E1 __` bị xóa thành `__ __ __`. **Không** publish `.../sequence`. Node-RED không nhận gì. | | |
| **TC-07** | Tay rời khung hình giữa chừng | Đang giữ `palm` được ~10 khung thì rút tay ra khỏi khung hình | Thanh tiến trình 15 khung tụt về 0. Overlay hiện `NONE 0.00`. Cử chỉ **không** được chấp nhận. Đưa tay lại phải giữ đủ 15 khung từ đầu. | | |
| **TC-08** | Thiếu khoảng `none` giữa 2 cử chỉ | Làm `palm` xong **giữ nguyên tay**, đổi thẳng sang `victory` mà không hạ tay | Sau khi nhận `palm`, thanh tiến trình chuyển màu cam kèm chữ "HA TAY XUONG". `victory` **không** được nhận cho tới khi có đủ 10 khung `none`. | | |
| **TC-09** | Cử chỉ mơ hồ, độ tin cậy thấp | Làm một cử chỉ nửa vời, không giống lớp nào (ví dụ co 3 ngón) | Overlay hiện tên lớp với `conf` < 0.70, chữ màu xám. Thanh tiến trình **không** tăng. Không cử chỉ nào được chấp nhận. | | |

---

## C. Nhóm mạng và độ bền

| Mã | Kịch bản | Đầu vào | Kết quả mong đợi | Kết quả thực tế | Đạt / Không |
|---|---|---|---|---|---|
| **TC-10** | Mất kết nối MQTT phía Python | Đang chạy `gesture_lock.py` thì tắt WiFi laptop ~15 giây rồi bật lại | Overlay chuyển `MQTT OFF` màu đỏ. **Cửa sổ video vẫn chạy mượt, không đơ** — đây là điểm cần chứng minh. Bật lại WiFi: tự kết nối lại, overlay về `MQTT ON`, không phải khởi động lại script. | | |
| **TC-11** | Mất kết nối phía ESP32 | Trên Wokwi, bấm Stop rồi Start lại | OLED hiện `WiFi:--  MQTT:--` rồi tự nối lại thành `OK`. Dashboard: ô "ESP32" chuyển "MẤT KẾT NỐI (…s trước)" trong vòng ~15 giây, rồi quay về "ONLINE". | | |
| **TC-12** | Đóng Node-RED giữa chừng | Tắt Node-RED, làm chuỗi đúng, rồi bật lại | Python vẫn publish bình thường (không lỗi). Không có lệnh nào gửi xuống ESP32 → servo không quay. Bật Node-RED lại: chuỗi mới hoạt động bình thường. Bản tin gửi lúc Node-RED tắt **bị mất** (QoS 0, không retain) — đây là hành vi đúng như thiết kế, cần nêu trong báo cáo. | | |

---

## D. Nhóm Dashboard (tầng 4)

| Mã | Kịch bản | Đầu vào | Kết quả mong đợi | Kết quả thực tế | Đạt / Không |
|---|---|---|---|---|---|
| **TC-13** | Mở khẩn cấp từ Dashboard | Ở trạng thái bình thường, bấm nút **"MỞ KHẨN CẤP"** | Node-RED publish thẳng `{"action":"unlock","ttl":5}` mà **không** qua khâu nhận diện cử chỉ. Servo quay 90°. Bảng lịch sử ghi "MO TU DASHBOARD". Đây là **luồng downlink thứ hai** của hệ thống. | | |
| **TC-14** | Mở khẩn cấp **trong lúc** lockout | Gây lockout (TC-03) rồi bấm "MỞ KHẨN CẤP" | Node-RED **có** gửi lệnh `unlock`, nhưng **ESP32 cố ý bỏ qua** — servo không quay, buzzer kêu 1 tiếng trầm báo đang bị khóa. Đây là hành vi **đúng theo thiết kế**, không phải lỗi: lockout chặn cả đường vòng. | | |
| **TC-15** | Reset lockout | Đang lockout, bấm nút **"RESET LOCKOUT"** | Node-RED xóa cờ và bộ đếm sai; đồng thời publish `{"action":"lockout","sec":0}` để ESP32 cũng thoát lockout. LED đỏ tắt, OLED về màn hình chờ. Sau đó "MỞ KHẨN CẤP" hoạt động lại bình thường. | | |
| **TC-16** | Bảng lịch sử và biểu đồ | Làm lẫn lộn vài lần đúng và vài lần sai | Bảng "10 lần truy cập gần nhất": dòng mới nhất **ở trên cùng**, tối đa 10 dòng, màu chữ đổi theo kết quả (xanh/cam/đỏ). Biểu đồ cột: số "Thành công" và "Thất bại" tăng đúng. | | |

---

## E. Nhóm dữ liệu

| Mã | Kịch bản | Đầu vào | Kết quả mong đợi | Kết quả thực tế | Đạt / Không |
|---|---|---|---|---|---|
| **TC-17** | Ghi log ra CSV | Sau khi chạy xong nhóm A, mở `middleware/access_log.csv` | File tồn tại, có dòng tiêu đề `timestamp,ma_nhap,ket_qua,so_lan_sai_lien_tiep`. Mỗi lần thử là 1 dòng. Cột `so_lan_sai_lien_tiep` tăng 1→2→3 rồi về 0 sau lần mở thành công. | | |
| **TC-18** | Độ chính xác model từng lớp, trên validation **chia theo burst** | Chạy toàn bộ `train_classifier.ipynb`, đọc ô **Bước 7** "Độ chính xác từng lớp". Validation chia theo `burst_id` (GroupShuffleSplit trong từng lớp, `random_state=42`): 30 mẫu của cùng một lần bấm R chỉ nằm ở train **hoặc** ở validation. | Ô Bước 3 in "khong burst nao nam o ca hai phia" và lớp nào cũng có burst trong validation. Ô Bước 7: **không có** cặp lớp nào nhầm nhau trên 10%. Nếu có, ô in "CẢNH BÁO" kèm tên cặp — phải xử lý trước khi quay demo. **Không** dùng con số của lần chia ngẫu nhiên (`train_test_split`) cũ làm căn cứ: các mẫu cùng burst nằm ở cả hai phía nên con số đó bị thổi phồng. | | |

---

## Chỗ dễ trượt khi test

1. **TC-04 và TC-14 là hai test quan trọng nhất về bảo mật.** Chúng chứng minh lockout
   chặn được **cả hai** đường vào: đường cử chỉ (TC-04) và đường dashboard (TC-14).
   Nếu chỉ test đường cử chỉ thì chưa chứng minh được gì nhiều.

2. **TC-10 chứng minh kiến trúc bất đồng bộ.** Nếu cửa sổ video bị đơ khi mất mạng
   nghĩa là MQTT đang chặn vòng lặp camera — sai thiết kế, phải sửa.

3. **Thu dữ liệu ở đúng chỗ và đúng ánh sáng sẽ demo.** Model học cả nền phía sau
   và điều kiện sáng. Thu ở phòng này rồi demo ở phòng khác là nguyên nhân trượt
   phổ biến nhất, và nó sẽ hiện ra ở TC-01 chứ không hiện ở TC-18.

4. **Broker công cộng có thể có người lạ publish vào topic của bạn.** Nếu thấy bản tin
   lạ khi chạy `mosquitto_sub`, hãy đổi prefix topic sang chuỗi ngẫu nhiên hơn.

---

## Tổng kết

| Nhóm | Số test | Đạt | Không đạt | Chưa test |
|---|---|---|---|---|
| A. Chức năng chính | 5 | | | |
| B. State machine | 4 | | | |
| C. Mạng và độ bền | 3 | | | |
| D. Dashboard | 4 | | | |
| E. Dữ liệu | 2 | | | |
| **Tổng** | **18** | | | |

**Người test:** ________________  **Ngày:** ________________
