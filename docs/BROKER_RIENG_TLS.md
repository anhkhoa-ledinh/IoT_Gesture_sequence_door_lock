# Broker riêng: TLS + tài khoản + phân quyền theo topic

Từ 31/10/2026 hệ thống có **hai chế độ**, chọn bằng một dòng trong `vision/config.json`:

| | `"dung_broker_rieng": false` (mặc định) | `"dung_broker_rieng": true` |
|---|---|---|
| Broker | `broker.hivemq.com:1883` công cộng | broker riêng EMQX, cổng **8883** |
| Mã hoá | không | **TLS**, kiểm chứng chỉ máy chủ |
| Đăng nhập | không | **mỗi chương trình một tài khoản** |
| Ai gửi được lệnh mở cửa `.../cmd` | **bất kỳ ai** biết topic | **chỉ Node-RED** |
| Ai đọc được mã `.../sequence` | bất kỳ ai | **chỉ Node-RED** (và tài khoản giám sát) |

Chế độ mặc định giữ nguyên để demo không bị ảnh hưởng nếu broker riêng có sự cố.

---

## 1. Vì sao cần

Với broker công cộng, đọc mã nguồn là biết topic, và:

- ai cũng gửi được `{"action":"unlock"}` vào `.../cmd` — ESP32 mở cửa, không cần camera hay mật mã;
- ai cũng gửi được `{"action":"lockout","sec":0}` rồi `unlock` — vượt luôn lockout;
- ai cũng nghe được `.../sequence` — thấy mã đúng mỗi lần chủ nhà mở cửa;
- trên đường truyền mọi thứ là chữ rõ.

Broker riêng chặn cả bốn: không có tài khoản thì không vào được; có tài khoản thì chỉ làm
được đúng phần việc của mình; đường truyền mã hoá TLS.

## 2. Bảng phân quyền (nguyên tắc "đặc quyền tối thiểu")

| Tài khoản | Chương trình | Được NGHE | Được GỬI |
|---|---|---|---|
| `gate_laptop` | `gesture_lock.py` | — | `.../gesture`, `.../sequence` |
| `gate_nodered` | Node-RED | `.../sequence`, `.../state` | `.../cmd` |
| `gate_esp32` | firmware ESP32 | `.../cmd`, `.../gesture` | `.../state` |
| `gate_giam_sat` | `dem_10_lan.py`, `kiem_truoc_khi_demo.py`, `kiem_tra_phan_quyen.py` | `.../#` | — |
| *mọi tài khoản khác / mọi topic khác* | | **cấm** | **cấm** |

Hệ quả đáng nói khi bảo vệ: **kể cả lấy được mật khẩu trong firmware ESP32** (thiết bị gắn
ở cửa, dễ bị tháo ra nhất) cũng **không** gửi được lệnh mở cửa, vì `gate_esp32` không có quyền
gửi `.../cmd`. Muốn mở cửa phải chiếm được Node-RED.

## 3. Cài đặt — khoảng 20 phút, làm một lần

### Bước 1. Tạo broker EMQX Serverless

Dùng **EMQX Cloud Serverless** vì gói này cho đặt luật phân quyền theo từng tài khoản và từng
topic (tối đa 100 luật mỗi tài khoản), chỉ mở cổng TLS 8883, không cho kết nối ẩn danh.
(HiveMQ Cloud Serverless không còn tạo cluster mới được, và mỗi tài khoản chỉ có một quyền.)

1. Đăng ký tài khoản tại trang EMQX Cloud, tạo **New Deployment → Serverless**, chọn vùng gần
   Việt Nam nhất có trong danh sách.
2. Ở trang **Overview** của deployment, chép **địa chỉ** (dạng `xxxxxxxx.ala.<vùng>.emqxsl.com`)
   và kiểm cổng **MQTT over TLS là 8883**.

> Giao diện EMQX có thể đổi tên menu theo thời gian. Nếu không thấy đúng tên dưới đây, tìm mục
> *Access Control* (Authentication / Authorization).

### Bước 2. Sinh tài khoản và các file cấu hình

```powershell
cd D:\IoT_Gesture_sequence_door_lock
.conda\python.exe scripts\tao_tai_khoan_mqtt.py --host xxxxxxxx.ala.<vùng>.emqxsl.com
```

Script sinh 4 mật khẩu ngẫu nhiên và ghi:

| File | Nội dung | Commit? |
|---|---|---|
| `vision/mqtt_tai_khoan.json` | 4 tài khoản | **KHÔNG** (đã có trong `.gitignore`) |
| `firmware/secrets.h` | host, cổng, tài khoản `gate_esp32` | **KHÔNG** |
| `middleware/flows_broker_rieng.json` | bản sao `flows.json` dùng TLS + tài khoản `gate_nodered` | **KHÔNG** |
| `vision/config.json` | ghi host, cổng vào `broker_rieng` (chưa bật) | có |

Rồi in ra **bảng tài khoản** và **bảng luật**.

### Bước 3. Nhập tài khoản và luật vào EMQX

1. **Access Control → Authentication → Add:** nhập 4 cặp username / password script vừa in.
2. **Access Control → Authorization → Add:** nhập lần lượt từng luật script in ra (cột tài khoản,
   topic, hành động, cho phép/cấm). **Luật cuối `All Users · # · Publish & Subscribe · Deny`
   bắt buộc phải có**: EMQX mặc định cho phép mọi thứ chưa có luật, luật này đổi sang "cấm tất
   cả, trừ những gì liệt kê".

### Bước 4. Kiểm tra phân quyền — trước khi đụng vào hệ thống

```powershell
.conda\python.exe scripts\kiem_tra_phan_quyen.py
```

Script kiểm 16 điều và ghi kết quả vào `docs/ket_qua_phan_quyen.md`:

- cổng 1883 không mở; không tài khoản hoặc sai mật khẩu thì bị từ chối;
- 4 tài khoản đều kết nối TLS được;
- `esp32`, `laptop` **không** nghe trộm được `.../sequence`;
- `laptop`, `esp32`, `giam_sat` **không** gửi được lệnh vào `.../cmd`; `laptop` không giả được `.../state`;
- đối chứng: `nodered` gửi `.../cmd` được, `laptop` gửi `.../gesture` được.

Lệnh thử gửi vào `.../cmd` là `{"action":"kiem_tra_acl"}`, firmware bỏ qua — chạy lúc hệ thống
đang hoạt động cũng an toàn. Script không gửi gì vào `.../sequence`.

**Phải 16/16 mới đi tiếp.** Dòng KHÔNG ĐẠT nào cũng chỉ thẳng luật đang thiếu.

### Bước 5. Chuyển cả ba phía sang broker riêng — cùng một lúc

1. **Node-RED:** Import `middleware/flows_broker_rieng.json` (chọn *Replace*) → Deploy → tắt và
   chạy lại `node-red` từ thư mục dự án. Node broker phải hiện *connected*. Nếu báo lỗi xác
   thực: mở node **EMQX rieng (TLS)** → tab *Security*, nhập `gate_nodered` và mật khẩu.
2. **ESP32:** VS Code → PlatformIO **Build** → Wokwi **Start Simulator**. Có `firmware/secrets.h`
   thì firmware tự dùng TLS. OLED phải hiện `MQTT:OK`. Lần kết nối đầu chậm hơn 1–3 giây vì bắt
   tay TLS.
3. **Python:** sửa `vision/config.json` → `"dung_broker_rieng": true`.
4. Chạy `scripts\kiem_truoc_khi_demo.py` — dòng broker phải ghi `(TLS, tai khoan giam_sat)`.

### Quay về broker công cộng (khi cần demo gấp)

`"dung_broker_rieng": false` · import lại `middleware/flows.json` · xoá (hoặc đổi tên)
`firmware/secrets.h` rồi Build lại.

## 4. Đã kiểm thử những gì (31/10/2026)

Chưa chạy trên EMQX thật (cần tài khoản của nhóm). Đã chạy trên **broker thử nghiệm cục bộ**
(aedes, chỉ mở TLS, bắt buộc đăng nhập, đúng bảng phân quyền ở mục 2, bỏ qua bản tin bị cấm
giống EMQX):

| Phép thử | Kết quả |
|---|---|
| `kiem_tra_phan_quyen.py` trên broker có phân quyền | **16/16 đạt** |
| Đối chứng: cùng script trên broker **không** phân quyền | 10/16 — bắt đúng **6** lỗ hổng (nghe trộm mã, gửi lệnh mở cửa từ 3 tài khoản, giả trạng thái) |
| Broker giả mạo (chứng chỉ không do CA tin cậy ký) | Python **từ chối kết nối**: `CERTIFICATE_VERIFY_FAILED` |
| `gesture_lock.py` (tài khoản laptop) gửi cử chỉ + mã qua TLS | tài khoản giám sát nhận đủ |
| Node-RED 4 nạp `flows_broker_rieng.json` | kết nối `mqtts://` bằng `gate_nodered`, đăng ký `.../sequence`, `.../state` |
| Đầu-cuối tầng 2–3: laptop gửi `7C4D3A` → Node-RED → ESP32 giả lập | nhận `{"action":"unlock","ttl":5}`; gửi mã sai → nhận `{"action":"deny"}` |
| `pytest` (thêm 11 test cho chế độ này) | 112 passed |

**Chưa kiểm được:** firmware chưa biên dịch được ở môi trường làm việc (không tải được bộ
biên dịch ESP32) — phải Build trên máy; kết nối TLS từ Wokwi tới EMQX thật.

## 5. Còn lại sau khi làm phần này

- **Mã vẫn đi dạng rõ trong broker** tới Node-RED và nằm rõ trong `access_log.csv`. TLS chỉ bảo
  vệ đường truyền. Hướng tiếp: HMAC mã trước khi gửi.
- **Ai chiếm được máy chạy Node-RED** thì vẫn mở được cửa — đó là "não" của hệ thống.
- **Mật khẩu ESP32 nằm trong firmware** — lấy được thì giả được trạng thái ổ khoá trên
  Dashboard (`.../state`), nhưng không mở được cửa.
- **Không gian mã vẫn 216 tổ hợp**; lockout 30 giây vẫn là lớp chống dò chính.
- Chứng chỉ gốc: gói `middleware/certs/emqx_ca_bundle.pem` gồm *DigiCert Global Root CA*
  (tài liệu EMQX ghi Serverless dùng chứng chỉ này) và *DigiCert Global Root G2*. Nếu EMQX đổi
  CA, tải file CA ở trang Overview của deployment, thay file trên, rồi tạo lại `firmware/ca_cert.h`
  (copy nội dung PEM vào giữa `R"PEM(` và `)PEM"`).
