# Việc còn lại trên máy (sau cập nhật 31/10/2026)

Những gì **đã xong** trong lần cập nhật này: thêm dữ liệu GitHub, train lại model (76.6% kiểm
định chéo, HaGRID 72.7%), chọn ngưỡng 0.80 và mã mới `7C4D3A` bằng số liệu, kiểm thử tự động
logic Node-RED (24/24) và pytest (101 passed), cập nhật báo cáo. Chi tiết:
`docs/ket_qua_cai_tien_train.md`.

Những việc dưới đây **cần camera, Wokwi và Node-RED chạy thật** nên phải làm trên máy. Làm
đúng thứ tự.

## 1. Nạp flow mới vào Node-RED (5 phút) — bắt buộc

Mã đã đổi từ `7CE13A` sang `7C4D3A` (`palm → ok → fist`). Node-RED đang giữ mã cũ trong bộ nhớ.

1. Mở `http://127.0.0.1:1880` → menu ☰ → **Import** → chọn `middleware/flows.json` →
   chọn **Replace** (thay flow cũ) → **Deploy**.
2. Tắt cửa sổ đang chạy `node-red` rồi chạy lại **từ thư mục dự án**:
   ```powershell
   cd D:\IoT_Gesture_sequence_door_lock
   node-red
   ```
   Khởi động lại là để xóa mã cũ trong flow context.

## 2. Build lại firmware và xác nhận servo quay (5 phút)

Firmware đã sửa buzzer sang kênh LEDC riêng nhưng **chưa ai thấy servo quay**.

1. VS Code → PlatformIO **Build (✓)** → đợi `SUCCESS`.
2. F1 → **Wokwi: Start Simulator** → đợi OLED hiện `WiFi:OK MQTT:OK`.
3. Bấm **MỞ KHẨN CẤP** trên dashboard → nhìn ngay servo và LED xanh (chỉ mở 5 giây).

## 3. Tiền kiểm (2 phút)

```powershell
.conda\python.exe scripts\kiem_truoc_khi_demo.py
```
Phải PASS hết. Nếu báo mã trong flow context khác `7C4D3A` → làm lại bước 1.

## 4. Chạy nhận diện với model mới

```powershell
.conda\python.exe vision\gesture_lock.py
```
Làm `palm` → hạ tay → `ok` → hạ tay → `fist`, mỗi cử chỉ **giữ yên** tới khi thanh xanh đầy.
Độ tin cậy giờ phải hiện 0.9+ (model cũ chỉ 0.45–0.54).

Nếu phải giữ tay quá lâu mới nhận: sửa `vision/config.json → thresholds.min_confidence` từ
`0.8` xuống `0.7` (đổi lại: tỉ lệ nhận sai tăng từ 2/76 lên 5/76 burst trong giả lập).

## 5. Đo 10 lần và điền test case (1–1.5 giờ)

```powershell
.conda\python.exe scripts\dem_10_lan.py --ghi-chu "model 31/10, ma 7C4D3A, nguong 0.8"
```
Sau đó chạy 18 kịch bản trong `docs/TEST_CASES.md`, điền cột "Kết quả thực tế". Trọng tâm:
TC-01, TC-04, TC-14 (lockout chặn cả nút mở khẩn cấp), TC-10 (mất mạng mà video không đơ).

## 6. Quay video demo

Theo `docs/KICH_BAN_QUAY_VIDEO.md` (đã cập nhật chuỗi mới `palm → ok → fist`).

## 7. Điền nốt báo cáo

Các ô `[CHƯA ĐO]` còn lại trong `docs/BAO_CAO_KY_THUAT.md` mục 6.2 đều lấy từ bước 5.

## 8. (Tuỳ chọn, nên làm) Chuyển sang broker riêng có TLS

Khoảng 20 phút, làm **sau** khi bước 1–5 đã chạy được trên broker công cộng, để nếu có trục
trặc còn biết lỗi nằm ở đâu: `docs/BROKER_RIENG_TLS.md`. Chạy `scripts\kiem_tra_phan_quyen.py`
phải 16/16 rồi mới bật `dung_broker_rieng`.
