# Báo cáo kỹ thuật

**AI Hand-Gesture Authenticated Smart Door Lock — A Four-Layer IoT System Using MediaPipe
Hand Landmark Classification and MQTT**

*Khóa cửa thông minh xác thực bằng chuỗi cử chỉ tay — hệ thống IoT bốn tầng*

> **Trạng thái tài liệu (24/10/2026):** bản khung. Mọi con số trong báo cáo đều kèm nguồn
> (file hoặc script sinh ra nó — xem Phụ lục). Chỗ nào chưa có số đo thật ghi **[CHƯA ĐO]**
> và sẽ được điền sau phiên chạy thật và sau khi chạy lại notebook huấn luyện.

---

## 1. Mục tiêu và phạm vi

Người dùng thực hiện một **chuỗi 3 cử chỉ tay** trước webcam. Mỗi cử chỉ được phân loại
bằng MediaPipe HandLandmarker cộng một mạng MLP nhỏ, rồi ánh xạ thành 1 byte hex; ghép 3
byte thành mật mã (mặc định `palm → victory → fist` = `7CE13A`). Middleware Node-RED kiểm
mã, đếm số lần sai, khóa tạm 30 giây sau 3 lần sai, và ra lệnh mở khóa cho ESP32.

**Trong phạm vi:**

- Hệ thống đủ 4 tầng: cảm biến (laptop + webcam), mạng (MQTT), middleware (Node-RED),
  ứng dụng (Node-RED Dashboard).
- Hai luồng uplink và hai luồng downlink chạy qua MQTT.
- 7 lớp cử chỉ: `fist`, `palm`, `victory`, `thumb_up`, `point_up`, `ok` và lớp phân cách
  `none`.
- Cơ chế bảo vệ: khóa tạm (lockout) sau 3 lần sai, chặn ở **cả** Node-RED lẫn firmware.

**Ngoài phạm vi:**

- Phần cứng thật: ESP32, servo, OLED, buzzer và LED đều mô phỏng trên Wokwi.
- Bảo mật kênh truyền: broker công cộng, không xác thực, không mã hóa (xem mục 7.2).
- Nhiều người dùng, nhiều cửa, quản lý mật mã từ xa.

Tham số hệ thống nằm tập trung trong `vision/config.json`:

| Tham số | Giá trị |
|---|---|
| Khung giữ ổn định để chấp nhận 1 cử chỉ | 15 |
| Độ tin cậy tối thiểu | 0.70 |
| Số khung `none` tối thiểu giữa 2 cử chỉ | 10 |
| Timeout chuỗi (tính từ cử chỉ được chấp nhận gần nhất) | 10 giây |
| Độ dài mã | 3 cử chỉ |
| Số lần sai trước lockout | 3 |
| Thời gian lockout | 30 giây |
| Servo đóng / mở, thời gian giữ mở | 0° / 90°, 5 giây |

---

## 2. Kiến trúc 4 tầng

### 2.1. Các tầng

| Tầng | Thành phần | Công nghệ | File | Nhiệm vụ |
|---|---|---|---|---|
| 1a — Sensing | laptop + webcam | Python, OpenCV, MediaPipe Tasks, TFLite | `vision/gesture_lock.py` | ảnh → cử chỉ → chuỗi mã → publish. **Không tự quyết định** mã đúng hay sai. |
| 1b — Actuating | ESP32 (Wokwi) | Arduino, PubSubClient, ESP32Servo, SSD1306 | `firmware/gate_lock.cpp` | nghe lệnh và thi hành: servo, LED, buzzer, OLED. Tự chặn `unlock` khi đang lockout. |
| 2 — Network | MQTT 3.1.1 | `broker.hivemq.com:1883`, QoS 0, không retain | — | chuyển bản tin giữa các thiết bị qua tên topic, không cần biết IP của nhau. |
| 3 — Middleware | Node-RED | function node JavaScript | `middleware/flows.json` | **nơi ra quyết định**: kiểm mã, đếm sai, lockout, ghi `access_log.csv`, watchdog ESP32. |
| 4 — Application | Node-RED Dashboard | node-red-dashboard | cùng `flows.json` | trạng thái khóa, 10 lần truy cập gần nhất, biểu đồ, nút "MỞ KHẨN CẤP" và "RESET LOCKOUT". |

Prefix topic: `huit/ak_majespecter/gate/`.

### 2.2. Luồng uplink (thiết bị → hệ thống)

| # | Topic | Publish → Subscribe | Khi nào | Payload |
|---|---|---|---|---|
| U1 | `huit/ak_majespecter/gate/gesture` | Python → ESP32 | mỗi khi chấp nhận 1 cử chỉ | `{"gesture":"victory","hex":"E1","conf":0.93,"ts":…}` |
| **U2** | `huit/ak_majespecter/gate/sequence` | Python → Node-RED | khi đủ 3 cử chỉ | `{"code":"7CE13A","ts":…}` |
| U3 | `huit/ak_majespecter/gate/state` | ESP32 → Node-RED | mỗi 5 giây và mỗi khi đổi trạng thái | `{"lock":"closed","attempts":0,"uptime":…}` |

**Luồng uplink chính là U2:** webcam → MediaPipe trích 21 điểm mốc → vector 42 chiều →
MLP phân loại → ghép 3 byte → publish `.../sequence` → Node-RED kiểm mã. U3 vừa đưa trạng
thái thật của ổ khóa lên Dashboard, vừa làm nhịp watchdog: quá 15 giây không nghe thấy thì
Dashboard báo "MẤT KẾT NỐI".

### 2.3. Luồng downlink (hệ thống → thiết bị)

| # | Topic | Publish → Subscribe | Khi nào | Payload |
|---|---|---|---|---|
| **D1** | `huit/ak_majespecter/gate/cmd` | Node-RED (function kiểm mã) → ESP32 | sau mỗi lần kiểm mã | `{"action":"unlock","ttl":5}` / `{"action":"deny"}` / `{"action":"lockout","sec":30}` |
| D2 | `huit/ak_majespecter/gate/cmd` | Node-RED (nút Dashboard) → ESP32 | bấm "MỞ KHẨN CẤP" / "RESET LOCKOUT" | `{"action":"unlock","ttl":5}` / `{"action":"lockout","sec":0}` |

D1 bắt nguồn từ tầng 3. D2 bắt nguồn từ **tầng 4** và đi thẳng xuống tầng 1b, không qua
khâu nhận diện — dùng khi camera hỏng hoặc người dùng không làm được cử chỉ. Lệnh
`lockout` với `sec: 0` là cách nút RESET xóa lockout phía ESP32 mà không thêm action thứ
tư ngoài đặc tả.

### 2.4. Một vòng hoàn chỉnh

```
[1a laptop] --U2 sequence--> [2 MQTT] --> [3 Node-RED] -- kiểm mã
                                                 |
[1b ESP32]  <--D1 cmd------- [2 MQTT] <----------┘
     └--U3 state--> [2 MQTT] --> [3 Node-RED] --> [4 Dashboard]
```

### 2.5. Vì sao tách hai node vật lý

1. **ESP32 không chạy nổi MediaPipe.** Riêng file `hand_landmarker.task` đã 7.8 MB
   (7 819 105 byte); ESP32 có 520 KB SRAM và thường 4 MB flash. Nhận dạng bắt buộc chạy
   trên máy mạnh hơn.
2. **Đúng mô hình IoT phân tán.** Node cảm biến và node chấp hành là hai thiết bị, ở hai
   nơi, chỉ liên hệ qua mạng. Gộp camera và servo vào một máy thì tầng Network vô nghĩa.
   Cách tách này cũng cho phép một Node-RED quản lý nhiều cửa chỉ bằng cách đổi prefix topic.
3. **Ràng buộc kỹ thuật cứng:** ESP32 mô phỏng chạy trên máy chủ của Wokwi, không thấy
   `localhost` hay mạng LAN của laptop. Vì vậy bắt buộc dùng broker công cộng — một
   Mosquitto cài trên laptop sẽ không bao giờ nối được với Wokwi.

### 2.6. Ba quyết định thiết kế đáng chú ý

- **Tầng 1a không tự lọc mã sai.** Python publish **mọi** chuỗi đủ 3 cử chỉ, kể cả chuỗi
  sai. Nếu Python tự chặn thì Node-RED không đếm được số lần sai và lockout không bao giờ
  kích hoạt.
- **Lockout chặn ở hai nơi.** Node-RED bỏ qua mọi `sequence` trong 30 giây lockout (vẫn ghi
  log "BI CHAN (dang lockout)"). Firmware độc lập bỏ qua `unlock` trong lúc lockout và kêu 1
  tiếng trầm — chặn cả đường vòng qua nút "MỞ KHẨN CẤP". Giới hạn của lớp chặn thứ hai: xem 7.2.
- **Không chặn vòng lặp.** Python dùng `connect_async()` + `loop_start()` để MQTT chạy luồng
  riêng — mất mạng không làm đơ cửa sổ camera (kịch bản TC-10). Firmware chạy toàn bộ
  bằng `millis()`, không có `delay()` nào.

---

## 3. Thiết kế máy trạng thái nhập mã

Lớp `SequenceStateMachine` (`vision/gesture_lock.py`) biến chuỗi `(nhãn, độ tin cậy)` từng
khung hình thành mật mã. Lớp này **thuần logic** — không dùng camera, mạng hay đồng hồ hệ
thống (thời gian truyền vào qua tham số) — nên được kiểm bằng dữ liệu giả trong
`vision/test_state_machine.py`.

| # | Điều kiện | Giá trị | Lý do | Test |
|---|---|---|---|---|
| 1 | Độ tin cậy softmax phải **≥ ngưỡng** thì khung đó mới được tích lũy | 0.70 | Một cử chỉ nửa vời hoặc tư thế chuyển tiếp thường cho xác suất dàn trải giữa các lớp. Không có ngưỡng thì mọi khung đều "là một lớp nào đó" và mã bị ghi rác. | `TestConfidenceThap` (3 test) |
| 2 | Cùng một nhãn phải giữ **liên tục** đủ số khung; một khung tụt ngưỡng hay đổi nhãn là đếm lại từ đầu | 15 khung (≈ 0.5 giây ở 30 fps) | Bộ phân loại dao động từng khung. Đòi giữ yên loại bỏ các cử chỉ bị "lướt qua" khi tay đang di chuyển — người dùng phải *có ý* làm cử chỉ đó. | `TestChuoiDung` (3 test) |
| 3 | Sau khi chấp nhận một cử chỉ, phải thấy lớp `none` đủ số khung **liên tục** mới nhận cử chỉ tiếp theo | 10 khung | Không có luật này, giữ yên một bàn tay 45 khung sẽ bị đếm thành 3 cử chỉ giống nhau và tự sinh ra mã. Nó cũng đánh dấu ranh giới rõ ràng giữa hai cử chỉ. Không cần `none` trước cử chỉ **đầu tiên**. | `TestKhoangNone` (4 test) |
| 4 | Quá thời gian kể từ cử chỉ được chấp nhận **gần nhất** mà chưa đủ chuỗi thì xóa hết | 10 giây | Người dùng bỏ đi giữa chừng thì chuỗi dở dang không được "treo" chờ người tiếp theo nối vào. Mỗi cử chỉ mới gia hạn đồng hồ; đồng hồ chỉ chạy sau cử chỉ đầu tiên. | `TestTimeout` (4 test) |

Đủ 3 cử chỉ thì phát sự kiện `on_sequence(code)` rồi tự reset. Phía Node-RED: mã đúng →
`unlock` và xóa bộ đếm sai; mã sai → tăng bộ đếm; đủ 3 lần sai → `lockout` 30 giây; trong
lockout → không trả lời lệnh nào nhưng vẫn ghi log. Mã hợp lệ được giữ trong *flow
context* của Node-RED (khởi tạo từ hằng `MA_MAC_DINH` ở lần kiểm mã đầu tiên) — hệ quả
vận hành của chi tiết này nêu ở mục 7.6.

---

## 4. Kết quả huấn luyện

### 4.1. Dữ liệu

Thu bằng `vision/collect_data.py` trên webcam của người làm đồ án. Mỗi lần bấm **R** ghi
30 mẫu liên tiếp cách nhau 2 khung hình — gọi là một **burst**.

| Lớp | Số mẫu ban đầu (26/09) | Sau vệ sinh (23/10) | Số burst | Số phiên thu |
|---|---|---|---|---|
| `fist` | 358 | 358 | 12 | 1 |
| `palm` | 398 | 398 | 14 | 1 |
| `victory` | 420 | 420 | 14 | 1 |
| `thumb_up` | 377 | 377 | 13 | 1 |
| `point_up` | 300 | 300 | 10 | 1 |
| `ok` | 374 | 374 | 13 | 1 |
| `none` | 367 | **277** | 10 | 1 |
| **Tổng** | **2 594** | **2 504** | **86** | **7** |

Vệ sinh ngày 23/10 bỏ đúng 3 burst lớp `none` (dòng 2228–2317 của file gốc, 90 mẫu). Ba
burst này được ghi ngay sau lớp `ok` và có 81%, 96%, 64% láng giềng gần nhất (ngoài burst
của chính nó) là mẫu `ok` — tức là bàn tay đang làm `ok` bị dán nhãn `none`. Bản gốc được
giữ nguyên tại `vision/model/keypoint_backup_20261023.csv`.

**Mỗi lớp được thu trong đúng một phiên liền mạch**, theo thứ tự cố định fist → palm →
victory → thumb_up → point_up → ok → none. Hệ quả nêu ở mục 7.5.

Vector đặc trưng 42 chiều (`vision/common.py`, `preprocess_landmarks`): lấy `(x, y)` của 21
điểm mốc, dời gốc về cổ tay, lật trục x nếu là tay trái, chia cho giá trị tuyệt đối lớn
nhất. Mạng: `Input(42) → Dropout(0.2) → Dense(20, relu) → Dropout(0.4) → Dense(10, relu) →
Dense(7, softmax)`, khoảng 1 nghìn tham số.

### 4.2. Phương pháp đánh giá

> **Ban đầu tập validation được chia ngẫu nhiên từng mẫu và bị rò rỉ burst.** Rò rỉ được
> phát hiện bằng phép thử láng giềng gần nhất bỏ burst (1-NN bỏ burst), và đã được sửa
> bằng `StratifiedGroupKFold` nhóm theo burst. Đây là nội dung chính của mục **7.1** — mục
> đó trình bày đầy đủ cách phát hiện, cách sửa và bài học.

| | Trước (26/09) | Sau (từ 24/10) |
|---|---|---|
| Cách chia | `train_test_split` 80/20 ngẫu nhiên từng mẫu, phân tầng theo lớp | `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)`, nhóm = `burst_id` |
| Mẫu của một burst | rải ra **cả** train lẫn validation | nằm trọn trong **một** fold |
| Con số báo cáo | độ chính xác trên 519 mẫu validation | trung bình ± độ lệch chuẩn qua 5 fold, ma trận nhầm lẫn gộp out-of-fold trên toàn bộ 2 504 mẫu |
| Độ chính xác tổng thể | **83.8%** (435/519) — *bị thổi phồng, không dùng làm căn cứ* | **[CHƯA ĐO]** |
| Model triển khai | model đánh giá (train trên 80%) | train lại trên 100% dữ liệu, số epoch = trung vị epoch tốt nhất của 5 fold |

Số liệu kiểm định chéo được notebook lưu ra `vision/model/eval_metrics.json`;
`vision/eval_external.py` đọc file này khi so với HaGRID chứ không tự chia lại dữ liệu.

### 4.3. Độ chính xác từng lớp

| Lớp | Validation ngẫu nhiên (26/09, **rò rỉ**) | 1-NN bỏ burst (23/10, sau vệ sinh) — *phép đo thô, không phải model* | 5 fold theo burst: trung bình ± độ lệch chuẩn | Out-of-fold |
|---|---|---|---|---|
| `fist` | 86.1% (62/72) | 66.5% | **[CHƯA ĐO]** | **[CHƯA ĐO]** |
| `palm` | 92.5% (74/80) | 85.4% | **[CHƯA ĐO]** | **[CHƯA ĐO]** |
| `victory` | 89.3% (75/84) | 52.4% | **[CHƯA ĐO]** | **[CHƯA ĐO]** |
| `thumb_up` | 84.0% (63/75) | 84.9% | **[CHƯA ĐO]** | **[CHƯA ĐO]** |
| `point_up` | 80.0% (48/60) | 61.7% | **[CHƯA ĐO]** | **[CHƯA ĐO]** |
| `ok` | 84.0% (63/75) | 89.0% | **[CHƯA ĐO]** | **[CHƯA ĐO]** |
| `none` | 68.5% (50/73) | 63.5% | **[CHƯA ĐO]** | **[CHƯA ĐO]** |
| **Tổng thể** | **83.8%** (435/519) | **72.4%** | **[CHƯA ĐO]** | **[CHƯA ĐO]** |

Cột "1-NN bỏ burst": với mỗi mẫu, tìm mẫu gần nhất **không cùng burst** trong không gian
đặc trưng 42 chiều, xem có cùng nhãn không. Nó không đo model mà đo xem mỗi lần ghi có
được các lần ghi khác cùng lớp "ủng hộ" hay không. Nó được đưa vào bảng vì là con số trung
thực duy nhất hiện có, trong lúc chờ chạy lại notebook.

### 4.4. Ma trận nhầm lẫn

`docs/confusion_matrix.png` hiện là ma trận của **lần chia ngẫu nhiên ngày 26/09** (rò rỉ).
Khi chạy lại notebook, file này bị thay bằng ma trận gộp out-of-fold của 5 fold:
**[CHƯA ĐO]**.

Để đối chiếu về sau, các cặp nhầm lớn nhất trên ma trận cũ (rò rỉ) là: `none → ok` 15.1%
(11/73), `thumb_up → fist` 14.7% (11/75), `ok → none` 13.3% (10/75), `point_up → victory`
10.0% (6/60). Phép 1-NN bỏ burst cho cùng các cặp đó, cộng thêm `victory ↔ point_up` và
`victory → none` nặng hơn nhiều (`victory → point_up` 88 mẫu, `victory → none` 81 mẫu trên
420).

### 4.5. Đánh giá trên tập ngoài HaGRID

HaGRID (Kapitanov và cộng sự, giấy phép CC BY-SA 4.0) được dùng làm **tập kiểm thử độc
lập**: không trộn vào huấn luyện (`USE_HAGRID_FOR_TRAINING = False`). Landmark được trích
trên Kaggle bằng cùng hàm tiền xử lý, có test kiểm hai bản chép khớp tuyệt đối
(`tests/test_preprocess_parity.py`). 300 mẫu mỗi lớp × 7 lớp = 2 100 mẫu.

> Số liệu dưới đây đo bằng **model ngày 26/09** (train trên 80% dữ liệu gốc). Sau khi train
> lại sẽ đo lại: **[CHƯA ĐO]**.

**Bóc tách 4 mức:**

| Phạm vi đánh giá | Số mẫu | Độ chính xác |
|---|---|---|
| Cả 7 lớp — **con số thô** | 2 100 | **53.8%** |
| Bỏ lớp `none` | 1 800 | 62.2% |
| Bỏ `none` + `thumb_up` | 1 500 | 73.1% |
| **Chỉ 3 cử chỉ trong mật mã** (`palm`, `victory`, `fist`) | 900 | **81.2%** |

**Vì sao con số thô thấp.** Hai lớp kéo con số xuống vì lý do không thuộc về khả năng
nhận dạng của model:

- **`none`: N/A — không so sánh được.** HaGRID `no_gesture` nghĩa là *có bàn tay trong
  khung nhưng không làm cử chỉ nào*, một tư thế tĩnh. Lớp `none` tự thu được thiết kế làm
  *dấu phân cách*, gồm cả tay đang chuyển động giữa hai cử chỉ. Hai định nghĩa khác nhau nên
  không có cơ sở so sánh; bảng từng lớp ghi N/A thay vì một con số.
- **`thumb_up`: 7.7% recall — do độ phân giải ảnh.** Ảnh HaGRID chụp người đứng xa tới 4 m;
  bàn tay chiếm trung vị 1.58% diện tích khung hình (`extract_report.json`). Ở kích thước đó
  ngón cái không phân giải nổi, nên `like` của HaGRID trông như bàn tay nắm và dồn vào `fist`.

Hai lớp đó cũng giải thích `fist` có precision chỉ 36.3%: `fist` được đoán 782/2 100 lần
vì `no_gesture` và `like` đều dồn vào nó.

| Lớp | Recall | Precision |
|---|---|---|
| `fist` | 94.7% | 36.3% |
| `palm` | 98.0% | 65.0% |
| `victory` | 51.0% | 60.5% |
| `thumb_up` | 7.7% | 50.0% |
| `point_up` | 71.0% | 96.4% |
| `ok` | 51.0% | 88.4% |
| `none` | N/A | N/A |

**Khoảng cách generalization so với dữ liệu tự thu: [CHƯA ĐO].** README trước đây so 83.8%
(validation rò rỉ, 7 lớp) với 81.2% (HaGRID, 3 lớp) và kết luận "cách nhau 2.6 điểm". Phép
so đó sai hai lần: con số tự thu bị thổi phồng, và hai bên không cùng phạm vi lớp. Sẽ so
lại khi có số out-of-fold, cùng phạm vi lớp ở cả hai phía.

---

## 5. Quyết định đổi mật mã

Ngày 27/09 (commit `489e803`) mật mã đổi từ `victory → palm → ok` (`E17C4D`) sang
`palm → victory → fist` (`7CE13A`). Lý do được lưu nguyên văn trong `vision/config.json`
→ `secret._ly_do_doi_ma`:

> Ma cu victory->palm->ok bi bo vi lop 'ok' nam trong hai trong ba cap nham nhau tren ma
> tran nham lan: none->ok 15.1% va ok->none 13.3%. Chieu none->ok nguy hiem nhat: mot ban
> tay vo nghia co the bi ghi nhan thanh mot byte ma va lam hong chuoi dang nhap. Ma moi chi
> dung ba lop chinh xac cao nhat: palm 92.5%, victory 89.3%, fist 86.1%. Lop 'ok' VAN la cu
> chi hop le va van nam trong model, chi khong dung trong mat ma.

**Đánh giá lại (24/10).** Mọi con số trong lý do trên đến từ validation chia ngẫu nhiên đã
bị rò rỉ burst (mục 7.1), nên không còn làm căn cứ được. Phép đo thô 1-NN bỏ burst cho thứ
tự gần như ngược lại: `victory` 52.4% là lớp yếu nhất, `fist` 66.5% đứng thứ ba từ dưới
lên, trong khi `ok` 89.0% là lớp tốt nhất. Về hướng thì lý do *chiều `none → ok` nguy
hiểm* vẫn đúng; về số thì chưa kết luận được. **Giữ hay đổi mã sẽ quyết định trên số liệu
kiểm định chéo 5 fold sau khi train lại: [CHƯA ĐO].** Mật mã hiện tại chưa bị đổi.

Không gian mã: 6 cử chỉ có mã × 3 vị trí, cho phép lặp → 6³ = **216** tổ hợp (tính từ cấu
hình, xem 7.2).

---

## 6. Kết quả kiểm thử

### 6.1. Kiểm thử đơn vị (không cần phần cứng)

`.conda\python.exe -m pytest` ngày 24/10/2026: **101 passed, 0 failed.**

| File | Kiểm gì |
|---|---|
| `vision/test_state_machine.py` | 4 điều kiện của máy trạng thái (mục 3), thay được bộ phân loại |
| `vision/test_common.py` | tiền xử lý landmark: bất biến dời chỗ / tỉ lệ, lật tay trái, không sinh NaN |
| `tests/test_preprocess_parity.py` | bản chép tiền xử lý trên Kaggle khớp tuyệt đối bản gốc |
| `tests/test_collect_meta.py` | `keypoint_meta.csv` luôn khớp từng dòng `keypoint.csv`; mỗi burst một nhãn |
| `tests/test_dem_10_lan.py` | phân loại lượt nhập mã từ chuỗi bản tin MQTT giả |
| `tests/test_kiem_truoc_khi_demo.py` | tiền kiểm: flow Node-RED đang chạy, mã trong flow context, file model |
| `tests/test_doc_access_log.py`, `tests/test_eval_external.py`, `tests/test_chan_doan_du_lieu.py` | công cụ đọc log, đọc số liệu đánh giá, chẩn đoán dữ liệu |

Kiểm thử đơn vị **không** chứng minh hệ thống chạy end-to-end.

### 6.2. Kiểm thử hệ thống

Đến ngày 23/10/2026: `middleware/access_log.csv` **chưa tồn tại** và chưa ô nào trong 18
test case được điền — **chưa có bằng chứng hệ thống từng chạy end-to-end.**

| Hạng mục | Kết quả | Nguồn |
|---|---|---|
| 10 lần nhập mã đúng, model 26/09 | **[CHƯA ĐO]** | `docs/ket_qua_10_lan.md` (sinh bởi `scripts/dem_10_lan.py`) |
| 10 lần nhập mã đúng, sau khi thu thêm dữ liệu và train lại | **[CHƯA ĐO]** | như trên, mục thứ hai |
| 18 test case | **[CHƯA ĐO]** | `docs/TEST_CASES.md` |
| TC-04 lockout chặn cả mã đúng | **[CHƯA ĐO]** | TC-04 |
| TC-14 lockout chặn cả nút mở khẩn cấp | **[CHƯA ĐO]** | TC-14 |
| TC-10 mất mạng mà video không đơ | **[CHƯA ĐO]** | TC-10 |
| TC-17 `access_log.csv` ghi đúng | **[CHƯA ĐO]** | TC-17, `docs/thong_ke_access_log.md` (sinh bởi `scripts/doc_access_log.py`) |
| Độ trễ `sequence` → `cmd` | **[CHƯA ĐO]** | cột "Trễ cmd" trong `docs/ket_qua_10_lan.md` |

---

## 7. Hạn chế và bài học

### 7.1. Đánh giá ban đầu bị rò rỉ burst — hạn chế lớn nhất và bài học chính

**Chuyện gì đã xảy ra.** Notebook ban đầu chia train/validation bằng
`train_test_split(test_size=0.2, stratify=y)` — ngẫu nhiên **từng mẫu**. Nhưng mẫu không
độc lập với nhau: 30 mẫu của một burst được ghi liên tiếp trong khoảng 2 giây, gần như cùng
một tư thế tay. Chia ngẫu nhiên xé mỗi burst ra hai phía, nên ở validation model gặp lại
đúng tư thế nó vừa học. Con số 83.8% đã được ghi vào README, dùng để so với HaGRID, và dùng
làm căn cứ đổi mật mã (mục 5).

**Phát hiện bằng cách nào** (`scripts/chan_doan_du_lieu.py`, mục 3b). Cùng một dữ liệu,
cùng phép thử k láng giềng gần nhất (k = 10) trong không gian 42 chiều, chỉ khác một điều:
có cho phép láng giềng nằm cùng burst hay không.

| Phép đo trên dữ liệu gốc 2 594 mẫu | Cho phép láng giềng cùng burst | **Bỏ** láng giềng cùng burst |
|---|---|---|
| Tỉ lệ mẫu có dưới một nửa láng giềng cùng nhãn | 4.4% | **37.4%** |
| 1-NN đúng nhãn | — | **69.7%** |

Nếu chỉ nhìn cột trái, dữ liệu trông "sạch". Cột phải cho thấy cái sạch đó gần như hoàn
toàn đến từ việc mỗi mẫu đứng cạnh 29 bản gần giống của chính nó. Khi bắt mỗi mẫu tìm
"đồng minh" ở *các lần ghi khác*, hơn một phần ba số mẫu thấy láng giềng của mình mang
nhãn khác. Kiểm thêm: thử chia nhóm theo burst bằng một lần `GroupShuffleSplit` với
`random_state=42` thì lớp `palm` không có burst nào trong validation; thử 1 000 seed thì
30% seed để trống ít nhất một lớp. Một lần chia nhóm vì thế cũng không đủ tin cậy.

**Đã sửa bằng cách nào.**

1. Ghi lại burst và phiên thu cho từng mẫu: `vision/model/keypoint_meta.csv`
   (`session_id`, `burst_id`). Dữ liệu cũ được suy burst theo thứ tự ghi; dữ liệu mới do
   `collect_data.py` ghi trực tiếp, và script từ chối chạy nếu hai file lệch dòng.
2. Bỏ 3 burst `none` dán nhãn sai (mục 4.1): 1-NN bỏ burst tăng từ 69.7% lên **72.4%**,
   riêng lớp `none` từ 50.7% lên 63.5%.
3. Đánh giá bằng `StratifiedGroupKFold(5)` nhóm theo `burst_id`: không burst nào nằm ở cả
   train lẫn validation, fold nào cũng đủ 7 lớp (notebook *assert* điều này), mỗi mẫu được
   chấm đúng một lần bởi model chưa từng học burst của nó.
4. Tách bạch hai thứ: **con số báo cáo** là của kiểm định chéo; **model triển khai** là bản
   train lại trên toàn bộ dữ liệu và không có con số đánh giá riêng.

**Số liệu trước / sau.**

| | Trước | Sau |
|---|---|---|
| Độ chính xác validation tổng thể | 83.8% — rò rỉ | **[CHƯA ĐO]** (kiểm định chéo 5 fold, chạy sau khi thu thêm dữ liệu) |
| 1-NN bỏ burst | 69.7% (2 594 mẫu) | 72.4% (2 504 mẫu, sau vệ sinh) |
| Mẫu có < 50% láng giềng ngoài burst cùng nhãn | 37.4% | 33.9% |

Chênh lệch 83.8% → 69.7% **không** phải là độ chính xác thật của model giảm 14 điểm (1-NN
không phải model). Nó là bằng chứng con số 83.8% không đo được điều cần đo.

**Hệ quả phải sửa theo:** câu "khoảng cách generalization 2.6 điểm" trong README, lý do đổi
mật mã trong `config.json`, tiêu chí TC-18, và cách `eval_external.py` lấy số validation
(trước đây nó tự chia lại dữ liệu theo đúng cách rò rỉ cũ).

**Bài học.**

- **Một con số validation chỉ trung thực bằng cách chia dữ liệu.** Khi các mẫu liên quan
  với nhau (khung hình liền kề, cùng người, cùng phiên), phải chia theo nhóm. Chia ngẫu
  nhiên từng mẫu là mặc định sai cho dữ liệu video.
- **Ghi metadata ngay lúc thu.** Dữ liệu cũ phải suy burst bằng heuristic; nếu
  `collect_data.py` ghi `burst_id` từ đầu thì đã không cần.
- **Một phép đo rẻ có thể quyết định.** Phép 1-NN bỏ burst chạy vài giây, không cần train,
  và trả lời câu hỏi mà điểm validation không trả lời được.
- **So sánh phải cùng phạm vi.** 7 lớp với 3 lớp, hay validation rò rỉ với tập ngoài, đều
  không cho ra một "khoảng cách" có nghĩa.

**Hạn chế còn lại của cách đánh giá mới:**

- Chia theo burst đo khả năng nhận ra *một lần làm cử chỉ mới*, nhưng các burst cùng phiên
  vẫn chung ánh sáng và chỗ ngồi. Muốn đo khả năng sang *điều kiện mới* phải chia theo
  `session_id`, cần từ 3 phiên thu mới trở lên.
- EarlyStopping chọn epoch dựa trên chính fold validation, nên con số mỗi fold lạc quan hơn
  một chút so với dữ liệu hoàn toàn mới.

### 7.2. Broker công cộng không có xác thực và mã hóa

`broker.hivemq.com:1883` không xác thực, không TLS. **Tiền tố topic chỉ để tránh trùng với
người khác, không phải biện pháp bảo mật** — tên topic nằm trong mã nguồn và trong mọi bản
tin. Đọc mã firmware và flow cho thấy cụ thể:

- Ai biết topic đều publish được `{"action":"unlock"}` vào `.../cmd`, và ESP32 mở khóa —
  không cần camera, không cần mật mã.
- Lớp chặn lockout ở firmware chỉ chặn `unlock`. Nó **không** chặn được người gửi
  `{"action":"lockout","sec":0}` trước (lệnh mà nút RESET dùng) rồi gửi `unlock`.
- Ai subscribe `.../sequence` đều thấy mật mã đúng dạng rõ mỗi lần chủ nhà mở khóa.
- Gửi thẳng mã vào `.../sequence` để dò: 216 tổ hợp, 3 lần thử mỗi chu kỳ lockout 30 giây →
  tối đa 72 chu kỳ ≈ **36 phút** để thử hết (tính từ cấu hình, chưa đo).

Đây là đánh đổi có chủ ý để chạy được với Wokwi (mục 2.5, lý do 3), không phải thiết kế
cho hệ thống thật.

### 7.3. Mật mã cử chỉ dễ bị nhìn trộm hơn bàn phím số

Cử chỉ tay to và lộ ra ngoài: người đứng sau thấy rõ cả ba cử chỉ, trong khi bàn phím có
thể che bằng tay kia. Không gian mã cũng nhỏ: 216 tổ hợp so với 10 000 của mã PIN 4 số.
Lockout làm chậm việc dò nhưng không bù được việc mã bị nhìn thấy.

### 7.4. Vector đặc trưng chỉ dùng toạ độ 2D

`preprocess_landmarks` chỉ lấy `(x, y)` và bỏ `z`, nên mất chiều sâu. Với `thumb_up` và
`fist`, khác biệt chính là ngón cái dựng lên hay gập vào — nhìn thẳng từ camera, hai tư thế
này chiếu xuống mặt phẳng ảnh gần giống nhau. Bằng chứng có ở cả ba nguồn: ma trận nhầm lẫn
cũ (`thumb_up → fist` 11/75), 1-NN bỏ burst (`fist → thumb_up` 60 mẫu, `thumb_up → fist` 46
mẫu), và HaGRID (`thumb_up` recall 7.7%, dồn vào `fist`). Vector cũng không chuẩn hóa góc
xoay, nên cùng một cử chỉ ở hai góc nghiêng cho hai vector cách xa nhau.

### 7.5. Dữ liệu một người, một webcam, một điều kiện ánh sáng

Toàn bộ dữ liệu huấn luyện do một người thu trên một webcam. Nặng hơn nữa: **mỗi lớp được
thu trong đúng một phiên**, theo thứ tự cố định. Lớp và bối cảnh của phiên (ánh sáng lúc
đó, chỗ ngồi, khoảng cách) trùng nhau hoàn toàn, nên model có thể học cả bối cảnh thay vì
chỉ học hình dạng bàn tay. Con số thô 53.8% trên HaGRID — người khác, máy ảnh khác — là
dấu hiệu của giới hạn này. Kế hoạch thu thêm: 3 phiên ngắn, mỗi phiên đủ cả 7 lớp xen kẽ,
đổi hẳn điều kiện giữa các phiên.

### 7.6. Các hạn chế vận hành khác

- **QoS 0, không retain:** bản tin gửi lúc Node-RED đang tắt bị mất (TC-12). Đúng thiết kế
  cho một ổ khóa — không muốn một lệnh cũ được phát lại — nhưng phải biết.
- **Mã hợp lệ nằm trong flow context.** Hàm kiểm mã chỉ đọc hằng `MA_MAC_DINH` khi context
  còn trống. Import flow mới với mã mới **không** đổi được mã đang chạy nếu context đã có
  mã cũ. Với cấu hình hiện tại (context lưu bộ nhớ, `contextStorage` không bật trong
  `settings.js`), khởi động lại Node-RED là xóa được; nếu chuyển sang lưu file thì không.
  `scripts/kiem_truoc_khi_demo.py` kiểm điều này trước mỗi phiên.
- **`access_log.csv` ghi mã nhập dạng rõ**, kể cả mã đúng mỗi lần mở thành công.
- **Mô phỏng, không phải phần cứng thật:** chưa có số liệu về nguồn cấp cho servo, nhiễu,
  hay độ trễ WiFi thật.

---

## 8. Hướng phát triển

1. **Broker riêng kèm TLS và xác thực.** Ví dụ Mosquitto hoặc HiveMQ Cloud, cổng 8883, tài
   khoản riêng cho từng thiết bị, ACL theo topic: chỉ Node-RED được publish `.../cmd`, chỉ
   laptop được publish `.../sequence`. Đây là thay đổi giải quyết được phần lớn mục 7.2.
2. **Băm SHA-256 chuỗi mã trước khi lưu.** Flow context và `access_log.csv` chỉ giữ giá trị
   băm, không giữ mã rõ. Vì không gian mã chỉ có 216 tổ hợp, băm trần dò ngược được ngay —
   phải dùng HMAC với khóa bí mật hoặc thêm salt, và lockout vẫn là lớp phòng thủ chính.
3. **Mở rộng vector đặc trưng lên 3D:** thêm `z` của 21 điểm mốc (63 chiều) hoặc dùng world
   landmarks của MediaPipe, cộng chuẩn hóa góc xoay. Mục tiêu trực tiếp: tách được
   `thumb_up` / `fist`.
4. **Mô hình phần cứng thật:** ESP32 DevKit, servo SG90 có nguồn 5 V riêng, OLED SSD1306;
   đo độ trễ đầu-cuối thật.
5. **Dữ liệu và đánh giá:** thu nhiều phiên, nhiều người, nhiều điều kiện; khi đủ phiên thì
   đánh giá chia theo `session_id` thay vì theo burst.

---

## Phụ lục — Nguồn của từng con số

| Con số | Nguồn |
|---|---|
| Số mẫu, số burst, số phiên mỗi lớp | `vision/model/keypoint.csv` + `keypoint_meta.csv`; `scripts/chan_doan_du_lieu.py` mục 1 |
| 3 burst `none` dán nhãn sai (81% / 96% / 64%) | `scripts/chan_doan_du_lieu.py` mục 3c, chạy trên dữ liệu gốc ngày 23/10 |
| 83.8% và độ chính xác từng lớp của validation ngẫu nhiên | `docs/confusion_matrix.png` (commit `06a3416`, 26/09) |
| 4.4% / 37.4% / 69.7% (dữ liệu gốc); 33.9% / 72.4% và từng lớp (sau vệ sinh) | `scripts/chan_doan_du_lieu.py` mục 3b |
| `palm` 0 burst validation khi chia một lần; 30% seed để trống một lớp | phép thử `GroupShuffleSplit` trên dữ liệu đã vệ sinh, 23/10; ghi lại trong markdown Bước 3 của notebook ở commit `d305068` |
| Bóc tách 4 mức HaGRID, recall/precision từng lớp, `bbox_area_frac` 1.58% | `vision/eval_external.py` với model 26/09; `vision/model/extract_report.json`; README mục 7.2.1 |
| 216 tổ hợp, 36 phút dò toàn bộ | tính từ `vision/config.json` (6 cử chỉ, 3 vị trí, 3 lần sai, 30 giây) |
| 101 unit test pass | `.conda\python.exe -m pytest`, 24/10/2026 |
| Số liệu kiểm định chéo 5 fold | `vision/model/eval_metrics.json` — **[CHƯA ĐO]** |
| 10 lần nhập mã | `docs/ket_qua_10_lan.md` — **[CHƯA ĐO]** |
| 18 test case | `docs/TEST_CASES.md` — **[CHƯA ĐO]** |
