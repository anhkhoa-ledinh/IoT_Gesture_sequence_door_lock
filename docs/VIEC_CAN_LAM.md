# Việc cần làm — hướng dẫn từng bước

Tài liệu này là **danh sách việc bạn phải tự làm**, xếp theo đúng thứ tự phụ thuộc.
Mỗi việc có 4 phần: **Làm gì** · **Kết quả đúng** · **Nếu sai** · **Mất bao lâu**.

Phần code đã viết xong và đã kiểm chứng. Những việc dưới đây là phần cần webcam,
cần tay người thao tác, hoặc cần môi trường bên ngoài (Wokwi, Node-RED, Kaggle) —
máy không tự làm thay được.

> **Đọc file nào?**
> · **File này** — danh sách việc, theo thứ tự, kèm cách xử lý khi sai. Đọc từ trên xuống.
> · [`HUONG_DAN_CHAY.md`](HUONG_DAN_CHAY.md) — tài liệu tra cứu: giải thích từng tham số,
>   bảng phím, ý nghĩa từng vùng overlay. Tra khi cần, không đọc tuần tự.

---

## Trạng thái hiện tại

Đo trực tiếp trên đĩa, ngày 25/09/2026:

| Thứ | Trạng thái | Ghi chú |
|---|---|---|
| Môi trường Python `.conda/` | ✅ có | đã kiểm chứng: opencv 5.0.0, mediapipe 0.10.31, tf 2.21.0 |
| `hand_landmarker.task` | ✅ có | 7.6 MB, đã tải tự động |
| Toàn bộ code + tài liệu | ✅ có | 26 unittest + 8 pytest, tất cả pass |
| Tiền tố topic MQTT | ✅ `huit/ak_majespecter/gate/` | đã đổi từ `ueh/` |
| `vision/model/keypoint.csv` | ❌ **chưa có** | chưa thu dữ liệu |
| `gesture_classifier.tflite` | ❌ **chưa có** | chưa train |
| `docs/confusion_matrix.png` | ❌ chưa có | sinh ra khi train |
| `keypoint_hagrid.csv` | ❌ chưa có | chưa chạy Kaggle |
| `middleware/access_log.csv` | ❌ chưa có | sinh ra khi Node-RED chạy lần đầu |

**Wokwi và Node-RED** nằm ngoài máy nên không kiểm tra được từ đây — bạn tự biết đã
dựng chưa.

---

## Thứ tự phụ thuộc — đọc cái này trước

```
 A. Wokwi          ──┐
 B. Node-RED       ──┼──> C. Kiểm MQTT (ESP32 <-> Node-RED)
                     │
 D. Thu dữ liệu ──> E. Train ──> F. Chạy end-to-end ──> H. Điền test case
                                        ▲                      │
 G. Kaggle HaGRID ──────────────────────┴──> I. eval_external  │
                                                               │
                                              J. README + video demo
```

**Ba điều quan trọng về thứ tự:**

1. **A và B làm được ngay**, không cần chờ gì. Làm xong là đã chứng minh được luồng
   downlink hoạt động, dù chưa có camera.
2. **D → E → F là chuỗi bắt buộc.** Không có dữ liệu thì không train được, không có
   model thì `gesture_lock.py` không chạy được.
3. **G (Kaggle) độc lập** với D/E — chạy song song được. Nhưng **I (`eval_external.py`)
   cần cả G và E**, vì nó so model đã train với dữ liệu HaGRID.

**Đường ngắn nhất để thấy hệ thống chạy:** làm A → B → C. Mất khoảng 40 phút và bạn
thấy servo quay. Chỉ sau đó mới đáng bỏ 1 tiếng thu dữ liệu.

---

# A. Dựng ESP32 trên Wokwi

⏱ **20–30 phút** (lần đầu), **3 phút** (nếu chỉ dán lại sau khi đổi prefix)

### Làm gì

1. Vào **wokwi.com**, đăng nhập (Google hoặc GitHub đều được).
2. **New Project** → chọn **ESP32** → **ESP32 DevKit V1**.
3. Tab **Library Manager** (ở panel bên trái, cạnh tab `diagram.json`) → bấm
   **+ Add a library** → thêm lần lượt **6** thư viện, gõ đúng tên:

   ```
   PubSubClient
   ArduinoJson
   ESP32Servo
   Adafruit SSD1306
   Adafruit GFX Library
   Adafruit BusIO
   ```

   > `WiFi.h` và `Wire.h` đã có sẵn trong ESP32 core — **không** thêm vào đây.
   > Danh sách này cũng nằm ở [`firmware/libraries.txt`](../firmware/libraries.txt).

4. Mở tab **`sketch.ino`** → **chọn hết (Ctrl+A) → xóa** → dán toàn bộ nội dung
   [`firmware/gate_lock.ino`](../firmware/gate_lock.ino).
5. Mở tab **`diagram.json`** → **chọn hết → xóa** → dán toàn bộ
   [`firmware/diagram.json`](../firmware/diagram.json).
6. Bấm **▶ Start** (nút tam giác xanh).

### Kết quả đúng

Màn hình OLED hiện đúng 5 dòng này:

```
WiFi:OK  MQTT:OK
READY - show code
LOCKED
CODE __ __ __
So lan sai: 0
```

Servo ở góc 0°. Cả hai LED đều tắt.

### Nếu sai

| Hiện tượng | Nguyên nhân · Cách sửa |
|---|---|
| Wokwi báo đỏ ở một dây trong `diagram.json` | Tên chân GND không khớp bản Wokwi. **Sửa `esp:GND.2` hoặc `esp:GND.3` thành `esp:GND.1`** — mọi GND nối chung một mạch, đổi không ảnh hưởng gì. |
| Lỗi biên dịch `'xxx' was not declared` | Thiếu thư viện. Kiểm lại đủ 6 cái ở bước 3, **đúng chính tả**, rồi Start lại. |
| `WiFi:--` mãi không lên `OK` | Kiểm trong code: SSID `"Wokwi-GUEST"`, mật khẩu **rỗng** `""`, channel `6`. Cả ba phải đúng. |
| `MQTT:--` nhưng `WiFi:OK` | Broker công cộng đôi lúc quá tải. **Đợi 30 giây** — firmware tự thử lại mỗi 3 giây. Quá 2 phút vẫn `--` thì Stop rồi Start lại. |
| OLED trống hoàn toàn | Dây SDA/SCL sai. Kiểm `oled1:SDA → esp:D21` và `oled1:SCL → esp:D22`. |
| Servo giật, hoặc buzzer không kêu | Xung đột bộ đếm LEDC giữa `ESP32Servo` và `tone()`. **Báo lại cho tôi** — phương án dự phòng là đổi sang `ledcWriteTone` với kênh cố định. Đây là rủi ro tôi đã lường trước nhưng không kiểm chứng được vì không biên dịch được ở máy. |

---

## A′. Cách khác — extension Wokwi trên VS Code

⏱ **40–60 phút lần đầu** (phần lớn là tải toolchain)

Dùng cách này **hoặc** cách A ở trên, không cần cả hai. Hai file cấu hình đã tạo sẵn:
[`platformio.ini`](../platformio.ini) và [`firmware/wokwi.toml`](../firmware/wokwi.toml).

### Khác biệt cốt lõi so với web

**Extension VS Code KHÔNG biên dịch code.** Readme của chính nó nói: *"using the
firmware binaries from your project"* — nó chỉ **mô phỏng** file `.bin` đã build sẵn.
Web IDE tự biên dịch `.ino`; extension thì bạn phải tự build.

Nên cần **thêm một toolchain build**. Dự án này chọn PlatformIO vì nó tự tải đúng 6
thư viện, không phải bấm thêm gì.

**Đổi lại bạn được một thứ đáng giá:** `firmware/gate_lock.ino` trở thành **nguồn duy
nhất**. Sửa file là build lại rồi Wokwi tự nạp firmware mới — **không còn phải dán tay**,
nên cũng không còn rủi ro quên dán lại sau khi đổi prefix (xem cảnh báo cuối mục A).

### Làm gì

**A′1. Cài extension PlatformIO IDE.**
Ctrl+Shift+X → gõ `platformio` → cài **PlatformIO IDE** (`platformio.platformio-ide`).

> ⚠️ Lần build đầu PlatformIO tải toolchain ESP32 khoảng **300–500 MB**. Cần mạng tốt
> và khoảng 15–25 phút. Đây là lý do chính khiến cách này lâu hơn web.

**A′2. Kích hoạt license Wokwi.**
`F1` → **Wokwi: Request a New License** → làm theo trang web mở ra. Extension là sản
phẩm thương mại, có license miễn phí cho dùng phi thương mại — đọc điều khoản hiện ra
để tự xác nhận trường hợp của bạn.

**A′3. Build firmware.**
`F1` → **PlatformIO: Build** (hoặc bấm dấu **✓** trên thanh trạng thái dưới).

Xong phải có hai file:
```
.pio/build/esp32dev/firmware.bin
.pio/build/esp32dev/firmware.elf
```

**A′4. Chỉ cho Wokwi file cấu hình.**
`F1` → **Wokwi: Select Config File** → chọn `firmware/wokwi.toml`.

> Vì sao `wokwi.toml` nằm trong `firmware/` chứ không ở gốc: extension tìm
> `diagram.json` **cùng thư mục** với `wokwi.toml`. Đặt ở đó thì dùng chung luôn
> `firmware/diagram.json` đã có, không phải tạo bản sao thứ hai — bản sao là chỗ hai
> file lệch nhau về sau.

**A′5. Chạy.**
`F1` → **Wokwi: Start Simulator**.

### Kết quả đúng

Panel mô phỏng mở trong VS Code, hiện đúng sơ đồ mạch, và OLED hiện **cùng 5 dòng** như
cách A:

```
WiFi:OK  MQTT:OK
READY - show code
LOCKED
CODE __ __ __
So lan sai: 0
```

WiFi và MQTT chạy được vì extension có sẵn WiFi gateway (module `wokwigw`, `engine.wasm`)
— không phải cấu hình thêm gì cho `Wokwi-GUEST` hay `broker.hivemq.com`.

### Vòng lặp sửa code từ đây trở đi

```
sửa firmware/gate_lock.ino  →  PlatformIO: Build  →  Wokwi tự nạp lại và khởi động lại
```

Extension theo dõi file firmware và tự reload, không phải Start lại bằng tay.

### Nếu sai

| Hiện tượng | Nguyên nhân · Cách sửa |
|---|---|
| Wokwi báo **không tìm thấy firmware** | Đường dẫn trong `wokwi.toml` đang tính từ thư mục `firmware/`. Nếu extension tính từ gốc dự án thì **bỏ hai dấu `../`** đi — comment trong file đã ghi sẵn cả hai biến thể. |
| `PlatformIO: Build` không có trong F1 | Chưa cài xong extension PlatformIO, hoặc chưa reload VS Code. Ctrl+Shift+P → **Developer: Reload Window**. |
| Build lỗi `Library ... not found` | Sai định danh trong `lib_deps`. Mở [`platformio.ini`](../platformio.ini), so với **PlatformIO Registry** (`platformio.org/lib`). Định danh PlatformIO khác tên trong Arduino Library Manager. |
| Build lỗi ở `JsonDocument doc;` | ArduinoJson bị giải về bản v6. Kiểm dòng `bblanchon/ArduinoJson@^7.0.0` trong `platformio.ini` — code dùng API v7. |
| Build lỗi `ESP32PWM ... not declared` | `ESP32Servo` chưa tải được. Xóa thư mục `.pio/` rồi Build lại. |
| Wokwi đòi license | Làm A′2. Không có license thì extension không chạy. |
| Không thấy output `Serial.begin(115200)` | Extension mở serial trong terminal tích hợp riêng. Xem tab **Terminal** hoặc panel Wokwi. |
| Cần tiết kiệm thời gian / mạng yếu | **Quay về cách A (web wokwi.com).** Web không cần toolchain, không cần license, không tải 500 MB. Về mặt kết quả demo thì hai cách giống nhau. |

### Có nên chọn cách này không

| | Web wokwi.com | Extension VS Code |
|---|---|---|
| Cần toolchain | không | **có** — PlatformIO 300–500 MB |
| Cần license | không | **có** |
| Setup lần đầu | 20–30 phút | 40–60 phút |
| Sửa code | **dán tay** mỗi lần | build → tự reload |
| Nguồn code | bản dán, dễ lệch file gốc | **file gốc, không lệch** |
| Debug bằng GDB | không | có |

**Nếu chỉ cần demo xong đồ án:** cách A nhanh hơn, ít thứ có thể hỏng hơn.
**Nếu còn sửa firmware nhiều lần:** cách A′ đáng bỏ công, vì hết phải dán tay.

---

> **⚠️ Nếu bạn đã dựng Wokwi TRƯỚC khi đổi prefix `ueh/` → `huit/`:**
> code trên Wokwi là bản dán tay, **nó không tự cập nhật theo file trên đĩa**.
> Phải làm lại bước 4 (dán lại `sketch.ino`). Không dán lại thì ESP32 vẫn nghe topic
> `ueh/...` cũ, Node-RED gửi vào `huit/...`, và **hai bên không thấy nhau** — triệu chứng
> sẽ trông y như MQTT hỏng, rất mất thời gian truy.

---

# B. Dựng Node-RED

⏱ **20–30 phút** (lần đầu), **3 phút** (nếu chỉ import lại)

### Làm gì

**B1. Cài Node-RED** (bỏ qua nếu đã có):

```powershell
npm install -g --unsafe-perm node-red
```

**B2. Chạy:**

```powershell
node-red
```

Để cửa sổ này mở suốt. Mở trình duyệt vào **http://localhost:1880**

**B3. Cài dashboard** — đây là gói **duy nhất** phải cài thêm:

☰ (góc trên phải) → **Manage palette** → tab **Install** → gõ `node-red-dashboard`
→ bấm **Install** → xác nhận. Đợi cài xong rồi đóng.

**B4. Xóa flow cũ nếu có** — bước này quan trọng:

Nếu bạn **đã từng import** `flows.json` trước đây: **nhấp phải vào tab flow cũ**
(tên `Khoa cua cu chi`) → **Delete** → **Deploy**.

> Vì sao phải xóa trước: import lần hai sẽ trùng ID node. Node-RED sẽ hỏi bạn chọn
> giữa thay thế và tạo bản sao — nếu chọn sai bạn có **hai** flow cùng chạy, cả hai
> cùng nghe `.../sequence`, và mỗi lần nhập mã sẽ bị xử lý **hai lần** (đếm số lần sai
> nhảy 2 đơn vị, lockout đến sớm gấp đôi). Xóa trước là cách chắc chắn nhất.

**B5. Import flow:**

☰ → **Import** → dán **toàn bộ** nội dung [`middleware/flows.json`](../middleware/flows.json)
→ **Import** → **Deploy** (nút đỏ góc trên phải).

**B6. Sửa đường dẫn file log** — chỉ cần nếu dự án **không** nằm ở
`D:\IoT_Gesture_sequence_door_lock`:

Tìm node màu vàng nhạt tên **`access_log.csv`** → nhấp đôi → ô **Filename** → sửa
thành đường dẫn tuyệt đối đúng máy bạn → **Done** → **Deploy**.

> Node-RED giải đường dẫn tương đối theo `~/.node-red`, **không** theo thư mục dự án.
> Nên ở đây buộc phải để đường dẫn tuyệt đối.

**B7. Mở dashboard:** **http://localhost:1880/ui**

### Kết quả đúng

Trên dashboard:

- Ô **"Trạng thái ổ khóa"**: chữ to `DA KHOA` màu đỏ
- Ô **"ESP32"**: `ONLINE (nghe Ns truoc)` — xuất hiện trong vòng 15 giây nếu Wokwi
  đang chạy
- Bảng **"10 lần truy cập gần nhất"**: `chua co lan truy cap nao`
- Biểu đồ: `chua co lan thu nao`

Trong editor (localhost:1880), dưới node `Kiem ma` có dòng trạng thái nhỏ.

### Nếu sai

| Hiện tượng | Nguyên nhân · Cách sửa |
|---|---|
| Import báo `Unknown node type: ui_template` (hoặc `ui_chart`, `ui_button`, `ui_text`) | Chưa cài `node-red-dashboard`. Làm lại B3, rồi Deploy. |
| Ô "ESP32" hiện `CHUA NHAN DUOC TIN NAO` | Wokwi chưa chạy, **hoặc** Wokwi đang dùng prefix `ueh/` cũ. Kiểm việc A. |
| `http://localhost:1880/ui` báo 404 | Dashboard cài rồi nhưng chưa Deploy. Bấm Deploy. |
| Bảng lịch sử không hiện gì dù đã thử mã | Node `access_log.csv` báo lỗi đỏ → xem B6. |

---

# C. Kiểm tra MQTT — bước chốt của việc A + B

⏱ **5 phút**

### Làm gì

**C1.** Cài `mosquitto-clients` nếu chưa có (Windows: tải Mosquitto từ
mosquitto.org/download, hoặc dùng `winget install EclipseFoundation.Mosquitto`).

**C2.** Mở một cửa sổ terminal **riêng**, để nó chạy suốt:

```bash
mosquitto_sub -h broker.hivemq.com -p 1883 -t "huit/ak_majespecter/gate/#" -v
```

**C3.** Đợi 10 giây. Phải thấy ESP32 tự báo trạng thái:

```
huit/ak_majespecter/gate/state {"lock":"closed","attempts":0,"uptime":15}
huit/ak_majespecter/gate/state {"lock":"closed","attempts":0,"uptime":20}
```

**C4.** Bấm nút **"MỞ KHẨN CẤP"** trên dashboard. Phải thấy ngay:

```
huit/ak_majespecter/gate/cmd {"action":"unlock","ttl":5}
huit/ak_majespecter/gate/state {"lock":"open","attempts":0,"uptime":23}
```

Và **servo trên Wokwi quay 90°**, LED xanh sáng, OLED hiện `ACCESS GRANTED`, sau 5
giây servo tự về 0°.

### Kết quả đúng

Thấy đủ **cả hai chiều**: `state` đi lên (uplink) và `cmd` đi xuống (downlink).
Servo quay thật.

**Đến đây bạn đã chứng minh được 3 trong 4 tầng hoạt động** (tầng 1b, 2, 3, 4) mà
chưa cần camera. Đây là mốc đáng chụp ảnh lưu lại.

### Nếu sai

| Hiện tượng | Nguyên nhân · Cách sửa |
|---|---|
| Không thấy `state` nào | Wokwi không chạy, hoặc còn prefix `ueh/`. Dán lại `sketch.ino`. |
| Thấy `cmd` nhưng servo không quay | ESP32 đang nghe prefix khác. Cùng nguyên nhân trên. |
| Thấy `state` nhưng bấm nút không ra `cmd` | Node-RED chưa Deploy, hoặc node `mqtt out` báo lỗi đỏ. |
| Thấy message **lạ** không phải của bạn | Broker công cộng, có người dùng trùng topic. Đổi `mqtt.topic_prefix` trong `config.json` sang chuỗi ngẫu nhiên hơn rồi làm lại A + B. |

> **Lưu ý về "MỞ KHẨN CẤP" khi đang lockout:** nút này sẽ **không** làm servo quay nếu
> ESP32 đang trong 30 giây lockout. Đó là **cố ý** — firmware chặn mọi lệnh `unlock`
> trong thời gian lockout, kể cả lệnh đến từ dashboard. Muốn mở thì bấm
> **"RESET LOCKOUT"** trước. Đây là test case TC-14.

---

# D. Thu dữ liệu huấn luyện

⏱ **40–60 phút** — việc lâu nhất, và **quyết định toàn bộ chất lượng demo**

### Làm gì

```powershell
cd D:\IoT_Gesture_sequence_door_lock
.\.conda\python.exe vision\collect_data.py
```

### Phím điều khiển

| Phím | Tác dụng |
|---|---|
| `0`–`6` | chọn lớp cần thu |
| `SPACE` | ghi **1** mẫu |
| `R` | ghi liên tục **30** mẫu, cách nhau 2 khung |
| `Q` / `ESC` | thoát và in bảng đếm |

### Bảng lớp

| Phím | Lớp | Cử chỉ |
|---|---|---|
| `0` | `fist` | nắm tay |
| `1` | `palm` | xòe bàn tay, 5 ngón tách ra |
| `2` | `victory` | chữ V (ngón trỏ + giữa) |
| `3` | `thumb_up` | ngón cái chỉ lên, 4 ngón kia gập |
| `4` | `point_up` | ngón trỏ chỉ lên, 4 ngón kia gập |
| `5` | `ok` | ngón cái + trỏ chạm nhau thành vòng tròn |
| `6` | `none` | **không có tay / tay ở tư thế linh tinh** |

### Cách thu cho nhanh và đúng

Với **mỗi** lớp từ 0 đến 6:

1. Bấm số của lớp.
2. Làm cử chỉ, giữ yên.
3. Bấm `R` → ghi 30 mẫu.
4. **Đổi góc tay một chút** rồi bấm `R` lần nữa. Lặp **9–10 lần**.

Mỗi lần `R` hãy đổi một thứ:
- xoay cổ tay (nghiêng trái, nghiêng phải, hơi úp, hơi ngửa)
- đưa tay gần camera rồi lui ra xa
- dịch tay sang trái / sang phải / lên / xuống trong khung hình
- đổi tay (thu cả tay trái lẫn tay phải — code tự quy về tay phải nên vẫn dùng chung
  được, nhưng thu cả hai thì chắc hơn)

**Mục tiêu: 250–300 mẫu mỗi lớp.** Overlay hiện số đếm từng lớp, không phải tự nhớ.

### Riêng lớp `none` — đây là lớp hay bị thu qua loa nhất

Lớp `none` là **trạng thái phân cách** giữa hai cử chỉ. Không có nó thì giữ yên một
bàn tay 45 khung sẽ bị đếm thành 3 cử chỉ giống nhau và tự sinh ra một mật mã.

Thu `none` gồm **cả ba** loại sau, mỗi loại khoảng 100 mẫu:
- **không có tay** trong khung hình
- tay đang **chuyển động giữa hai cử chỉ** (nửa nắm nửa xòe)
- tư thế linh tinh không thuộc 6 lớp kia (co 3 ngón, bàn tay úp, tay che mặt...)

### Kết quả đúng

Khi bấm `Q`, script in bảng:

```
TONG KET SO MAU TRONG ...\vision\model\keypoint.csv
id  lop           so mau
0   fist             287
1   palm             291
...
6   none             305
                    2043  tong cong
```

Không lớp nào có dòng `<-- con it`.

### ⚠️ Cảnh báo lớn nhất của cả dự án

**Thu dữ liệu tại đúng chỗ và đúng ánh sáng mà bạn sẽ demo.**

Model học cả nền phía sau và điều kiện ánh sáng, không chỉ học hình dạng bàn tay. Thu
ở phòng trọ buổi tối rồi demo ở phòng học buổi sáng là **nguyên nhân trượt phổ biến
nhất**.

Điều khó chịu nhất: lỗi này **không hiện ra trong ma trận nhầm lẫn**. Ma trận vẫn đẹp,
độ chính xác vẫn 98%, vì tập validation cũng thu cùng chỗ đó. Nó chỉ hiện ra lúc bạn
đứng trước hội đồng.

Nếu chưa biết sẽ demo ở đâu: **thu ở 2–3 chỗ khác nhau**, mỗi chỗ một phần dữ liệu.

### Nếu sai

| Hiện tượng | Cách sửa |
|---|---|
| `LOI: khong mo duoc webcam index 0` | Sửa `camera.camera_index` trong [`vision/config.json`](../vision/config.json) thành `1` rồi `2`. |
| Overlay hiện `KHONG THAY TAY` dù tay đang trong khung | Thiếu sáng, hoặc tay quá xa. Bật thêm đèn, đưa tay gần hơn. |
| Bấm `SPACE` báo `Khong thay tay, khong ghi` | Đúng hành vi — không thấy tay thì không ghi rác vào CSV. Đưa tay vào khung rồi bấm lại. |
| Thu sai lớp, muốn xóa | Mở `vision/model/keypoint.csv` bằng editor, xóa các dòng cuối (mỗi dòng 1 mẫu, cột đầu là `class_id`). |

> Chạy lại `collect_data.py` nhiều lần được — dữ liệu **ghi thêm vào cuối**, không bao
> giờ ghi đè.

---

# E. Huấn luyện model

⏱ **10–15 phút**

### Làm gì

```powershell
cd D:\IoT_Gesture_sequence_door_lock
.\.conda\python.exe -m jupyter lab
```

Trình duyệt tự mở. Mở [`vision/train_classifier.ipynb`](../vision/train_classifier.ipynb)
→ menu **Run** → **Run All Cells**.

### Ba thứ phải kiểm, theo thứ tự

**E1. Cell "Bước 2" — phân bố lớp.** Không lớp nào có `<-- qua it`. Có thì quay lại D
thu thêm cho lớp đó.

**E2. Ô đối chiếu TFLite** (gần cuối). Phải in:

```
Ty le TFLite trung khop voi Keras: 100.0000%
OK - file .tflite dung duoc cho gesture_lock.py
```

Dưới 99.9% → **đừng dùng file `.tflite` đó**, báo lại cho tôi. Lý do ô này quan trọng:
nếu chuyển đổi TFLite hỏng, nó **không báo lỗi** — model vẫn chạy, vẫn trả về số, chỉ
là số **sai**. Bạn sẽ ngồi debug `gesture_lock.py` trong khi lỗi nằm ở đây.

**E3. Cell cuối cùng — cảnh báo cặp lớp nhầm nhau.** Đây là ô quyết định.

Nếu in `OK - khong co cap lop nao nham nhau qua 10%` → xong, sang việc F.

Nếu in `CANH BAO`, đọc kỹ dòng cuối cùng:

- In `Cac cu chi trong mat ma khong nam trong cap nham nao` → **chấp nhận được**, đi
  tiếp. Cặp bị nhầm không nằm trong mật mã `victory → palm → ok` nên không ảnh hưởng
  demo.
- In `NGHIEM TRONG: cac cu chi trong mat ma dang nam trong cap bi nham` → **phải xử
  lý**, chọn một trong hai:
  1. **Thu thêm** 100–150 mẫu cho **cả hai** lớp trong cặp bị nhầm, cố ý làm ở nhiều
     góc tay khác nhau, rồi chạy lại notebook.
  2. **Đổi mật mã** sang cặp cử chỉ khác — nhanh và chắc hơn. Sửa **hai** chỗ:
     - `secret.default_code` trong [`vision/config.json`](../vision/config.json)
     - `MA_MAC_DINH` trong [`middleware/flows.json`](../middleware/flows.json)
       (tìm trong function node `Kiem ma`), rồi **import lại flow** theo việc B.

> Vì sao ngưỡng 10% là nghiêm: mỗi cử chỉ đúng 90% thì cả chuỗi 3 cử chỉ chỉ còn
> `0.9³ ≈ 73%` — cứ 4 lần mở cửa hỏng 1 lần. Demo sẽ rất khổ.

### Kết quả đúng

Bốn file mới xuất hiện:

```
vision/model/gesture_classifier.keras
vision/model/gesture_classifier.tflite    <- file gesture_lock.py dùng
docs/confusion_matrix.png                 <- hình cho báo cáo
```

### Nếu sai

| Hiện tượng | Cách sửa |
|---|---|
| `FileNotFoundError: Chua co ...keypoint.csv` | Chưa làm việc D. |
| `loss: nan` ngay từ epoch đầu | CSV có dòng hỏng. Cell "Bước 2" đã kiểm NaN — nếu nó pass mà vẫn `nan` thì báo lại cho tôi. |
| `val_accuracy` cao ngay epoch 1 rồi đứng | Bình thường với bài này — đầu vào đã chuẩn hóa rất kỹ nên bài toán khá dễ. |
| Notebook dừng ở `assert data.shape[1] == 43` | CSV lẫn dữ liệu từ phiên bản tiền xử lý cũ. Xóa `keypoint.csv` và thu lại. |

---

# F. Chạy end-to-end

⏱ **15 phút**

### Làm gì

Đảm bảo **đang chạy đồng thời**: Wokwi (▶ Start), Node-RED (`node-red`), dashboard mở.
Rồi:

```powershell
cd D:\IoT_Gesture_sequence_door_lock
.\.conda\python.exe vision\gesture_lock.py
```

### Đọc overlay trên cửa sổ webcam

| Vùng | Ý nghĩa |
|---|---|
| Góc trên trái, chữ to | tên lớp + độ tin cậy. **Xanh** = đạt ngưỡng 0.70, **xám** = chưa đạt |
| Thanh xanh + `n/15` | đang giữ được bao nhiêu khung. Đủ 15 thì chốt cử chỉ |
| Thanh **cam** + `HA TAY XUONG` | vừa chốt 1 cử chỉ, phải hạ tay đủ 10 khung mới nhận cử chỉ tiếp |
| `MA: E1 7C __` | chuỗi hex đang nhập |
| Góc trên phải `con 7.3s` | đếm ngược timeout. Đỏ khi dưới 3 giây |
| Góc dưới phải `MQTT ON (5)` | trạng thái kết nối và số bản tin đã gửi |

Phím: `Q`/`ESC` thoát · `R` xóa chuỗi đang nhập.

### Thao tác chuẩn cho một lần mở khóa

```
1. Làm victory, GIỮ YÊN đến khi thanh xanh đầy      (~0.5 giây)
2. HẠ TAY xuống đến khi thanh cam đầy               (~0.3 giây)
3. Làm palm, giữ yên
4. Hạ tay
5. Làm ok, giữ yên
→ servo trên Wokwi quay, LED xanh, OLED "ACCESS GRANTED",
  dashboard hiện "MO KHOA", bảng lịch sử thêm 1 dòng
```

**Điểm hay sai nhất: phải GIỮ YÊN tay, không lướt qua.** Một khung tụt dưới 0.70 là
thanh tiến trình đếm lại từ 0.

### Kết quả đúng

Terminal in:

```
[chuoi] nhan 'victory' = E1 (conf 0.94)
[mqtt] -> huit/ak_majespecter/gate/gesture {"gesture":"victory","hex":"E1",...}
[chuoi] nhan 'palm' = 7C (conf 0.97)
...
[chuoi] DU 3 CU CHI -> ma E17C4D
[mqtt] -> huit/ak_majespecter/gate/sequence {"code":"E17C4D",...}
```

Và servo quay.

### Nếu sai

| Hiện tượng | Cách sửa |
|---|---|
| `FileNotFoundError: Chua co ...gesture_classifier.tflite` | Chưa làm việc E. |
| `MQTT OFF` màu đỏ | Kiểm mạng. Cửa sổ video **vẫn phải chạy mượt** — nếu nó đơ thì báo lại cho tôi, đó là lỗi thiết kế. |
| Nhận sai cử chỉ liên tục | Model yếu ở lớp đó. Xem lại E3, và kiểm ánh sáng có giống lúc thu dữ liệu không. |
| Thanh tiến trình không bao giờ đầy | Độ tin cậy dao động quanh 0.70. Thu thêm dữ liệu cho lớp đó, **hoặc** tạm hạ `thresholds.min_confidence` xuống `0.60` trong `config.json` để test (nhớ ghi lại là đã hạ, và nêu trong báo cáo). |
| Python publish nhưng servo không quay | Node-RED chưa nhận. Xem cửa sổ `mosquitto_sub` ở việc C để biết bản tin có lên broker không. |

---

# G. Trích dữ liệu HaGRID trên Kaggle

⏱ **30 phút setup + 1–3 tiếng chạy** (chạy thì để đó, không phải ngồi trông)

Việc này **độc lập** với D/E — làm song song được, ví dụ chạy Kaggle trong lúc thu dữ liệu.

### Mục đích — hiểu trước khi làm

HaGRID là **tập kiểm thử độc lập**, **không** trộn vào dữ liệu train. Model học từ tay
*của bạn*; HaGRID trả lời câu hỏi khác: *"model có nhận được tay người khác không"*.

**Con số trên HaGRID sẽ thấp hơn tập validation tự thu. Đó là kết quả đúng và trung
thực, không phải lỗi cần sửa.** Khoảng cách giữa hai con số chính là thứ đáng viết vào
báo cáo — nó đo mức độ model phụ thuộc vào người, nền và ánh sáng lúc thu dữ liệu.

### Làm gì

**G1. Bật Internet cho tài khoản Kaggle.** Cần **xác minh số điện thoại** trước:
kaggle.com → ảnh đại diện → **Settings** → **Phone Verification**. Không xác minh thì
không bật được Internet, và không bật Internet thì `pip install` trong notebook sẽ hỏng.

**G2. Tạo notebook.** kaggle.com/code → **New Notebook**. Trong notebook:
**File** → **Import Notebook** → chọn
[`kaggle/extract_hagrid_landmarks.ipynb`](../kaggle/extract_hagrid_landmarks.ipynb).

> Không tìm thấy mục Import Notebook thì làm cách thủ công: tạo notebook trống rồi
> copy từng cell từ file sang. 13 cell, mất khoảng 5 phút.

**G3. Thêm dataset HaGRID.** Panel bên phải → **Input** → **+ Add Input** → gõ `hagrid`.

Chọn bản nào:
- **Ưu tiên bản đã giảm kích thước** (tên thường có `512`, `512p`, `resized`). Bản gốc
  HaGRID nặng hàng trăm GB, đọc rất chậm.
- Bản được chọn phải có **cả ảnh lẫn file annotation `.json`**. Bản chỉ có ảnh đã crop
  sẵn theo lớp mà **không có annotation** thì thiếu bounding box và `leading_hand` —
  notebook sẽ không chạy đúng.
- Chưa chắc thì cứ thêm vào rồi **chạy Cell 1** — nó sẽ in ra cấu trúc thật và bạn biết
  ngay bản đó dùng được hay không.

**G4. Bật Internet.** Panel bên phải → **Settings** (hoặc mục Session options) →
**Internet** → **On**.

**G5. Chạy Cell 1 TRƯỚC, một mình nó.** Đừng Run All.

Đọc **hai mục** trong output:

- **Mục 3 — TEN LOP THAT.** Phải có đủ 7 tên: `fist`, `palm`, `peace`, `like`, `one`,
  `ok`, `no_gesture`. Thiếu tên nào thì Cell 4 sẽ tự dừng và báo — **đừng tự đoán ánh
  xạ thay thế**, báo lại cho tôi kèm danh sách tên thật.
- **Mục 5 — DINH DANG BOUNDING BOX.** Nó in ra dòng `-> DOAN: x,y,w,h` hoặc
  `-> DOAN: x1,y1,x2,y2`, kèm giá trị cụ thể. Nếu **không** phải `x,y,w,h` chuẩn hóa thì
  mở Cell 4 và sửa biến `BBOX_FORMAT` ở đầu cell thành một trong: `"xywh_abs"`,
  `"xyxy_norm"`, `"xyxy_abs"`.

**G6. Chạy Cell 2 → 3 → 4 → 5** lần lượt.

Cell 4 là cell lâu nhất. Nó in tiến độ từng lớp và ghi checkpoint mỗi 500 mẫu, nên
phiên Kaggle hết giờ giữa chừng cũng không mất hết.

**G7. Đọc bảng tóm tắt ở cuối Cell 5.** Xem mục "Nếu sai" bên dưới.

**G8. Tải 3 file về.** Panel bên phải → mục **Output** → tải từng file:

```
keypoint_hagrid.csv
keypoint_hagrid_meta.csv
extract_report.json
```

Không thấy mục Output thì bấm **Save Version** → **Quick Save** → đợi xong → mở version
đó → tab **Output** → tải.

**G9. Copy cả 3 file vào `D:\IoT_Gesture_sequence_door_lock\vision\model\`**

### Kết quả đúng

Cuối Cell 5 in:

```
OK — moi lop deu tren 50% va handedness khop tren 80%.
Tai 3 file tu /kaggle/working ve vision/model/ roi chay eval_external.py
```

### Nếu sai

Cell 5 tự in `*** DUNG LAI — CHUA DUOC DUA SO NAO VAO BAO CAO ***` khi gặp vấn đề.
**Đừng bỏ qua dòng này.** Xử lý theo bảng:

| Hiện tượng | Nguyên nhân · Cách sửa |
|---|---|
| Một lớp có tỉ lệ phát hiện **dưới 50%** | Theo thứ tự: (1) `BBOX_FORMAT` có đúng với output Cell 1 không; (2) thử tăng `BBOX_EXPAND` từ `0.20` lên `0.30`–`0.40` — bbox sát quá thì MediaPipe bị cắt mất đầu ngón tay. |
| Tỉ lệ khớp handedness **dưới 80%** | Kiểm `FLIP_TRUOC_MEDIAPIPE` có đang là `True`. Nếu đã `True` mà vẫn thấp, đó là dấu hiệu MediaPipe đọc sai tay trái/phải trên ảnh này (tay nhỏ, xa, mờ) — nghĩa là một phần dữ liệu đã bị lật nhầm và thành nhiễu. Báo lại cho tôi kèm con số. |
| `loi_doc_file` gần bằng `da_thu` | Cấu trúc thư mục ảnh của bản HaGRID này khác giả định trong hàm `tim_anh()`. **Đây là lỗi hay gặp nhất.** Báo lại cho tôi kèm output mục 7 của Cell 1 (danh sách thư mục ảnh), tôi sửa hàm tìm ảnh. |
| `SystemExit: Thieu lop [...]` | Bản HaGRID này đặt tên lớp khác. Báo lại kèm danh sách tên thật ở mục 3 Cell 1. |
| `pip install mediapipe` hỏng | Chưa bật Internet. Xem G4. |
| Phiên Kaggle hết giờ giữa Cell 4 | Giảm `MAX_PER_CLASS` từ `300` xuống `150` rồi chạy lại. 150 mẫu/lớp vẫn đủ để kết luận. |

---

# H. Đánh giá trên tập ngoài

⏱ **5 phút** · **cần xong cả E và G**

### Làm gì

```powershell
cd D:\IoT_Gesture_sequence_door_lock
.\.conda\python.exe vision\eval_external.py
```

### Kết quả đúng

Script in bảng hai con số cạnh nhau:

```
KHOANG CACH GENERALIZATION
Tap du lieu                                So mau    Do chinh xac
--------------------------------------------------------------
Validation tu thu (webcam nguoi dung)         409           xx.x%
HaGRID (tap ngoai, nguoi khac)               1847           xx.x%
--------------------------------------------------------------
Chenh lech                                                 +xx.x%
```

Và lưu `docs/confusion_matrix_hagrid.png`.

### Đọc con số thế nào

Script tự phân loại giúp bạn:

| Chênh lệch | Ý nghĩa |
|---|---|
| dưới 10% | model tổng quát hóa tốt ngoài mong đợi |
| 10–30% | **bình thường và đang mong đợi** cho bài này |
| trên 30% | model phụ thuộc nặng vào dữ liệu tự thu |

**Ghi cả hai con số vào báo cáo, đừng chỉ ghi con số cao hơn.** Con số HaGRID thấp hơn
là kết quả mong đợi. Báo cáo chỉ nêu con số 98% trên tập tự thu mà giấu con số tập ngoài
là chỗ người chấm hay hỏi tới.

### Nếu sai

| Hiện tượng | Cách sửa |
|---|---|
| `LOI: chua co ...gesture_classifier.tflite` | Chưa làm E. |
| `LOI: chua co ...keypoint_hagrid.csv` | Chưa làm G, hoặc chưa copy file vào `vision/model/`. |
| In `khop handedness ... <-- DUOI 80%` | Số liệu chưa đáng tin. Xem lại bảng "Nếu sai" của việc G. |
| Một cử chỉ trong mật mã dưới 70% ở tập ngoài | Script in `NGHIEM TRONG`. Nghĩa là người khác sẽ rất khó mở khóa này. Đổi mật mã hoặc thu thêm dữ liệu đa dạng hơn. |

---

# I. Điền test case

⏱ **45 phút**

### Làm gì

Mở [`docs/TEST_CASES.md`](TEST_CASES.md), chạy đủ **18 kịch bản**, điền cột
**"Kết quả thực tế"** và **"Đạt/Không"**.

Giữ cửa sổ `mosquitto_sub` (việc C) mở suốt để đối chiếu.

### Bốn test quan trọng nhất

| Mã | Vì sao quan trọng |
|---|---|
| **TC-04** | Làm **chuỗi ĐÚNG** trong lúc lockout → **vẫn bị chặn**. Chứng minh lockout chặn đường cử chỉ. |
| **TC-14** | Bấm **"MỞ KHẨN CẤP"** trong lúc lockout → **vẫn không quay servo**. Chứng minh lockout chặn cả đường vòng qua dashboard. |
| **TC-10** | Tắt WiFi laptop 15 giây → **cửa sổ video vẫn chạy mượt**, không đơ. Chứng minh MQTT không chặn vòng lặp camera. |
| **TC-18** | Không có cặp lớp nào nhầm nhau trên 10%. |

TC-04 và TC-14 đi **thành cặp**. Chỉ test một cái là chưa chứng minh được gì nhiều —
phải cho thấy lockout bịt **cả hai** đường vào.

---

# J. Hoàn thiện báo cáo

⏱ **30 phút + thời gian quay video**

### J1. Ghi nguồn và giấy phép HaGRID vào README

Dán đoạn này vào [`README.md`](../README.md), mục "Nguồn dữ liệu":

```markdown
## Nguồn dữ liệu ngoài

**HaGRID** — HAnd Gesture Recognition Image Dataset.
Kapitanov, Kvanchiani, Nagaev, Kraynov, Makhliarchuk.
Giấy phép: biến thể **Creative Commons BY-SA 4.0**.
Kho chính thức: https://github.com/hukenovs/hagrid

Dùng làm **tập kiểm thử độc lập**, không trộn vào dữ liệu huấn luyện.
Quy trình trích landmark: `kaggle/extract_hagrid_landmarks.ipynb`.
```

Phải ghi **cả tên dataset lẫn giấy phép** — trong cả README và báo cáo.

### J2. Quay video demo

**Bố cục: 3 cửa sổ cùng một khung hình.** Đây là cách chứng minh 4 tầng hoạt động thật,
rõ hơn mọi lời giải thích:

```
┌──────────────────────┬──────────────────────┐
│  webcam + overlay    │   Wokwi              │
│  (tầng 1a)           │   servo + OLED       │
│                      │   (tầng 1b)          │
├──────────────────────┴──────────────────────┤
│  Dashboard Node-RED (tầng 3 + 4)            │
└─────────────────────────────────────────────┘
```

Nội dung video, theo thứ tự:

1. **Mở khóa thành công** (TC-01)
2. **Nhập sai 3 lần → lockout** (TC-03)
3. **Làm chuỗi ĐÚNG trong lúc lockout → vẫn bị chặn** (TC-04) ← **cảnh ấn tượng nhất**
4. **Bấm "MỞ KHẨN CẤP" trong lúc lockout → vẫn không mở** (TC-14)
5. **Bấm "RESET LOCKOUT" rồi mở khẩn cấp → mở được** (TC-15, TC-13)

Lưu video vào `demo/` (thư mục này đã được `.gitignore` bỏ qua file `.mp4`).

### J3. Hình cho báo cáo

| File | Nội dung |
|---|---|
| `docs/confusion_matrix.png` | ma trận nhầm lẫn trên tập validation tự thu |
| `docs/confusion_matrix_hagrid.png` | ma trận nhầm lẫn trên tập ngoài HaGRID |
| sơ đồ 4 tầng | có sẵn dạng text trong [`KIEN_TRUC_4_TANG.md`](KIEN_TRUC_4_TANG.md) |
| `middleware/access_log.csv` | bảng log truy cập thật |

---

## Tổng thời gian

| Việc | Thời gian |
|---|---|
| A. Wokwi | 20–30 phút |
| B. Node-RED | 20–30 phút |
| C. Kiểm MQTT | 5 phút |
| D. Thu dữ liệu | **40–60 phút** |
| E. Train | 10–15 phút |
| F. Chạy end-to-end | 15 phút |
| G. Kaggle HaGRID | 30 phút setup + 1–3 tiếng chạy (song song được) |
| H. Đánh giá tập ngoài | 5 phút |
| I. Điền test case | 45 phút |
| J. Báo cáo + video | 30 phút + quay |
| **Tổng công sức** | **khoảng 4–5 tiếng**, chưa tính thời gian Kaggle chạy nền |

**Gợi ý chia buổi:**

- **Buổi 1 (1 tiếng):** A → B → C. Hết buổi bạn thấy servo quay. Đây là mốc tinh thần
  quan trọng nhất.
- **Buổi 2 (1.5 tiếng):** khởi động G (Kaggle) cho chạy nền → làm D → E → F.
- **Buổi 3 (1.5 tiếng):** H → I → J.

---

## Khi bế tắc, báo lại kèm những thứ này

Để tôi chẩn đoán được, gửi kèm:

1. **Lệnh đã chạy** và **output nguyên văn** (đừng tóm tắt lại — chữ trong lỗi quan trọng)
2. Với lỗi Wokwi: nội dung tab **Serial Monitor**
3. Với lỗi Node-RED: ảnh node bị đỏ + nội dung tab **Debug**
4. Với lỗi Kaggle: output **Cell 1** đầy đủ và output cuối **Cell 5**
5. Với nhận diện sai: bảng độ chính xác từng lớp ở cell cuối notebook train

Ba chỗ tôi **đã lường trước là có rủi ro** nhưng không kiểm chứng được từ máy, nên nếu
gặp thì gần như chắc là ở đây:

- **Xung đột LEDC giữa `ESP32Servo` và `tone()`** → servo giật hoặc buzzer câm (việc A)
- **Tên chân `esp:GND.2` / `GND.3` / `VIN`** trong `diagram.json` (việc A)
- **Hàm `tim_anh()`** đoán sai cấu trúc thư mục ảnh HaGRID (việc G)
