# Kết quả đo nhập mã trên hệ thống chạy thật

Sinh tự động bởi `scripts/dem_10_lan.py` (nghe MQTT, không đếm tay). Mỗi lần chạy script thêm một mục mới ở cuối file.

Một **lượt** mở khi có `.../sequence` và đóng khi có `.../cmd`. `KHÔNG PHẢN HỒI` = quá 5 giây không có `cmd`. `CHƯA ĐỦ MÃ` = Python đã nhận cử chỉ nhưng hết giờ trước khi đủ 3 cử chỉ, nên không gửi `sequence` nào.

## Lần đo 2026-10-31 08:17:38 → 08:20:28 — model 31/10, ma 7C4D3A, nguong 0.8

- Model: `gesture_classifier.tflite` sửa lúc 2026-10-31 05:51, md5 `7d2b1430`
- Mã đúng (`config.json` → `secret.default_code`): `7C4D3A`
- **Tổng số lượt: 18 — thành công 16 (88.9%)**
- Nhận diện ra đúng mã: 16/17 lượt có gửi `sequence`

| Kết quả | Số lượt |
|---|---|
| THÀNH CÔNG | 16 |
| TỪ CHỐI | 1 |
| KHÓA TẠM | 0 |
| KHÔNG PHẢN HỒI | 0 |
| CHƯA ĐỦ MÃ | 1 |

| # | Thời điểm | Mã nhận | Cử chỉ | Đúng mã? | Kết quả | Trễ `cmd` | Ghi chú |
|---|---|---|---|---|---|---|---|
| 1 | 08:18:01 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.22 s |  |
| 2 | 08:18:08 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.22 s |  |
| 3 | 08:18:12 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.22 s |  |
| 4 | 08:18:19 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.25 s |  |
| 5 | 08:18:27 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.21 s |  |
| 6 | 08:18:33 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.31 s |  |
| 7 | 08:18:38 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.83 s |  |
| 8 | 08:18:44 | `7C4D7C` | palm → ok → palm | **không** | TỪ CHỐI | 0.22 s |  |
| 9 | 08:18:50 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.20 s |  |
| 10 | 08:18:56 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.29 s |  |
| 11 | 08:19:00 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.25 s |  |
| 12 | 08:19:07 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.21 s |  |
| 13 | 08:19:14 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.24 s |  |
| 14 | 08:19:18 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.28 s |  |
| 15 | 08:19:43 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.22 s |  |
| 16 | 08:19:45 | `—` | palm → fist | — | CHƯA ĐỦ MÃ | — | 2 cu chi roi het gio phia Python |
| 17 | 08:20:04 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.26 s |  |
| 18 | 08:20:11 | `7C4D3A` | palm → ok → fist | có | THÀNH CÔNG | 0.21 s |  |
