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
| **TC-01** | Chuỗi đúng → mở khóa | Làm `palm` → hạ tay → `ok` → hạ tay → `fist`. Mỗi cử chỉ giữ yên ~1 giây. | Python publish `{"code":"7C4D3A",...}`. Node-RED publish `{"action":"unlock","ttl":5}`. Servo quay 90°, LED xanh sáng, OLED "ACCESS GRANTED", 1 tiếng bíp. Sau 5 giây servo tự về 0°. Dashboard hiện "ĐÃ MỞ" màu xanh. Bảng lịch sử thêm 1 dòng "DUNG — MO KHOA". | | |
| **TC-02** | Chuỗi sai → từ chối | Làm `thumb_up` → `thumb_up` → `thumb_up` (mã `B9B9B9`) | Node-RED publish `{"action":"deny"}`. LED đỏ nháy 3 lần, 2 tiếng bíp, OLED "ACCESS DENIED". Servo **không** quay. Dashboard hiện "TỪ CHỐI", ghi "SAI (lan 1/3)". | | |
| **TC-03** | Sai 3 lần liên tiếp → lockout | Lặp lại TC-02 ba lần liên tiếp, không xen kẽ lần đúng nào | Lần 1 và 2: `deny`. **Lần 3**: Node-RED publish `{"action":"lockout","sec":30}`. OLED đếm ngược từ 30, LED đỏ **sáng liên tục** (không nháy). Dashboard hiện "LOCKOUT". | | |
| **TC-04** | Thao tác trong lúc lockout | Ngay sau TC-03, làm **chuỗi ĐÚNG** `palm → ok → fist` | Node-RED **không gửi lệnh nào**. Servo không quay. OLED vẫn đếm ngược. Log ghi "BI CHAN (dang lockout)". Đây là điểm mấu chốt: **mã đúng cũng bị chặn**. | | |
| **TC-05** | Hết lockout → dùng lại bình thường | Đợi hết 30 giây rồi làm chuỗi đúng | LED đỏ tắt, OLED về màn hình chờ, bộ đếm sai về 0. Chuỗi đúng mở được khóa như TC-01. | | |

---

## B. Nhóm state machine phía Python

| Mã | Kịch bản | Đầu vào | Kết quả mong đợi | Kết quả thực tế | Đạt / Không |
|---|---|---|---|---|---|
| **TC-06** | Timeout giữa chừng | Làm `palm`, hạ tay, làm `ok`, rồi **bỏ đi hơn 10 giây** | Overlay đếm ngược từ 10.0s. Khi về 0: chuỗi `7C 4D __` bị xóa thành `__ __ __`. **Không** publish `.../sequence`. Node-RED không nhận gì. | | |
| **TC-07** | Tay rời khung hình giữa chừng | Đang giữ `palm` được ~10 khung thì rút tay ra khỏi khung hình | Thanh tiến trình 15 khung tụt về 0. Overlay hiện `NONE 0.00`. Cử chỉ **không** được chấp nhận. Đưa tay lại phải giữ đủ 15 khung từ đầu. | | |
| **TC-08** | Thiếu khoảng `none` giữa 2 cử chỉ | Làm `palm` xong **giữ nguyên tay**, đổi thẳng sang `victory` mà không hạ tay | Sau khi nhận `palm`, thanh tiến trình chuyển màu cam kèm chữ "HA TAY XUONG". `victory` **không** được nhận cho tới khi có đủ 10 khung `none`. | | |
| **TC-09** | Cử chỉ mơ hồ, độ tin cậy thấp | Làm một cử chỉ nửa vời, không giống lớp nào (ví dụ co 3 ngón) | Overlay hiện tên lớp với `conf` < 0.80, chữ màu xám. Thanh tiến trình **không** tăng. Không cử chỉ nào được chấp nhận. | | |

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
| **TC-18** | Độ chính xác model từng lớp, kiểm định chéo **chia theo burst** | Chạy toàn bộ `train_classifier.ipynb`, đọc ô **Bước 7** "Độ chính xác từng lớp". Đánh giá bằng `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)`, nhóm = `burst_id`: 30 mẫu của cùng một lần bấm R chỉ nằm ở train **hoặc** ở validation của mỗi fold. | Ô Bước 3 không báo lỗi assert (fold nào cũng đủ 7 lớp, mỗi mẫu nằm trong validation đúng 1 lần). Ô Bước 7 in độ chính xác từng lớp dạng trung bình ± độ lệch chuẩn qua 5 fold, và **không có** cặp lớp nào nhầm nhau trên 10% trong ma trận nhầm lẫn out-of-fold. Nếu có, ô in "CẢNH BÁO" kèm tên cặp — phải xử lý trước khi quay demo. Có file `vision/model/eval_metrics.json`. **Không** dùng con số của lần chia ngẫu nhiên (`train_test_split`) cũ làm căn cứ: các mẫu cùng burst nằm ở cả hai phía nên con số đó bị thổi phồng. | | |

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

---

## Kết quả kiểm thử tự động (31/10/2026)

Phần này **không** thay cho việc chạy tay 18 kịch bản ở trên: nó chỉ kiểm phần **logic** chạy
được mà không cần camera, ESP32 hay broker. Cột "Kết quả thực tế" ở các bảng trên vẫn để
trống cho lần chạy end-to-end.

### Logic tầng 3 (Node-RED) — `node tests/kiem_thu_flow_node.js`

Script đọc thẳng `middleware/flows.json`, chạy **đúng mã nguồn** của các node function với một
flow context giả và một đồng hồ giả (nên kiểm được lockout 30 giây mà không phải đợi).
Kết quả: **24/24 đạt**.

| TC | Phần logic đã kiểm | Kết quả |
|---|---|---|
| TC-01 | Mã đúng → `{"action":"unlock","ttl":5}`, log `DUNG — MO KHOA` | Đạt |
| TC-02 | Mã sai lần 1 → `deny`, log `SAI (lan 1/3)` | Đạt |
| TC-03 | Sai lần 3 → `{"action":"lockout","sec":30}` | Đạt |
| TC-04 | Đang lockout, nhập **mã đúng** → không gửi lệnh nào, log `BI CHAN (dang lockout)` | Đạt |
| TC-05 | Sau 31 giây → mã đúng mở được, bộ đếm sai về 0 | Đạt |
| TC-13 | Mở khẩn cấp → `unlock` không qua kiểm mã, log `MO TU DASHBOARD` | Đạt |
| TC-15 | Reset → gửi `lockout sec 0`, xóa cờ ở Node-RED, mã đúng mở được ngay | Đạt |
| TC-16 | Bảng lịch sử giữ 10 dòng, mới nhất trên cùng; biểu đồ đếm đúng | Đạt |
| TC-17 | Dòng CSV đủ 4 cột, `so_lan_sai_lien_tiep` = 1→2→3→3→0, timestamp ISO 8601 | Đạt |
| thêm | Mã viết thường vẫn được chấp nhận; bản tin rỗng tính là sai | Đạt |

**Chưa kiểm được bằng cách này:** servo/LED/OLED/buzzer (TC-01, 02, 03, 05 phía ESP32),
TC-14 (ESP32 bỏ qua `unlock` khi lockout — logic nằm trong firmware), TC-10/11/12 (mạng thật),
giao diện dashboard.

### Máy trạng thái phía Python và các công cụ — `.conda\python.exe -m pytest`

**112 passed** (31/10/2026, gồm 11 test cho chế độ broker riêng). Gồm 4 điều kiện của máy trạng thái (phần logic của TC-06, 07,
08, 09), tiền xử lý landmark, công cụ tiền kiểm, đếm 10 lần, đọc log.

### Bằng chứng từ lần chạy thật ngày 24/10

`middleware/access_log.csv` có 8 dòng `MO TU DASHBOARD` (24/10, 08:23–08:26 giờ VN) và OLED trên
Wokwi đổi sang `ACCESS GRANTED`: **đường downlink Dashboard → Node-RED → MQTT → ESP32 đã chạy
thật** (phần logic của TC-13). Servo chưa quay ở lần đó. Nguyên nhân nghi ngờ: `tone()` của buzzer tranh kênh LEDC với servo;
firmware đã sửa cho buzzer dùng kênh LEDC riêng — **cần chạy lại trên Wokwi để xác nhận**.

### TC-18 — kết quả notebook

| Tiêu chí | Kết quả |
|---|---|
| Ô Bước 3 không lỗi assert, fold nào cũng đủ 7 lớp | **Đạt** — 5 fold, 86 burst, mỗi mẫu validation đúng 1 lần |
| Có `vision/model/eval_metrics.json` | **Đạt** |
| Độ chính xác từng lớp, trung bình ± độ lệch qua 5 fold | fist 86.0 ± 10.1 · palm 88.9 ± 14.6 · victory 55.2 ± 28.6 · thumb_up 85.5 ± 16.8 · point_up 68.3 ± 8.7 · ok 79.3 ± 14.8 · none 69.8 ± 20.2 · **tổng 76.5 ± 4.3** |
| Không cặp lớp nào nhầm trên 10% | **Không đạt** — 5 cặp: victory→point_up 19.3%, point_up→victory 15.7%, thumb_up→fist 14.9%, victory→none 14.3%, point_up→none 12.0% |

Xử lý đã làm: đổi mật mã sang `palm → ok → fist` (không chứa `victory`, `point_up`,
`thumb_up`) và nâng ngưỡng lên 0.80 — chi tiết ở `docs/ket_qua_cai_tien_train.md`. Cặp
`thumb_up → fist` vẫn liên quan tới `fist` trong mã: người làm `thumb_up` có thể bị nhận thành
`fist` (giả lập ở ngưỡng 0.80 trên model cùng cấu hình: 2/13 burst `thumb_up` bị chấp nhận sai).

### Phân quyền broker riêng — `scripts/kiem_tra_phan_quyen.py`

Chỉ áp dụng khi dùng broker riêng (`docs/BROKER_RIENG_TLS.md`). Trên broker thử nghiệm cục bộ
ngày 31/10: **16/16 đạt**; đối chứng trên broker không phân quyền: script báo đúng 6 lỗ hổng.
Trên EMQX thật: **chưa chạy** — kết quả sẽ ghi vào `docs/ket_qua_phan_quyen.md`.
