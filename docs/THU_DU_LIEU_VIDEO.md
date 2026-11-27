# Thu thêm dữ liệu bằng video

Quay video, bỏ vào thư mục theo tên cử chỉ, chạy một lệnh là có dữ liệu train. **Không phải
gán nhãn từng khung hình**: mỗi video chỉ quay **một** cử chỉ, tên thư mục chính là nhãn.

## 1. Vì sao quay video tốt hơn bấm R

Dữ liệu cũ (`collect_data.py`) có một điểm yếu lớn: **một người, một buổi, một chỗ ngồi** cho
mỗi lớp. Model học thuộc điều kiện của buổi đó. Video quay bằng điện thoại cho phép thu nhiều
người, nhiều chỗ, nhiều kiểu ánh sáng trong một buổi chiều — đúng thứ đang thiếu.

## 2. Cách quay

**Mỗi video: 1 người · 1 cử chỉ · 1 tay · 5–10 giây.**

Trong lúc quay, giữ đúng cử chỉ nhưng **thay đổi chậm** những thứ dưới đây — mỗi video là một
cách nhìn khác của cùng cử chỉ:

- xoay cổ tay nhẹ trái/phải (±20°), nghiêng nhẹ trước/sau;
- đưa tay gần rồi xa camera (tay chiếm khoảng 1/6 đến 1/2 chiều cao khung);
- dịch tay qua lại trong khung.

Đổi giữa các video:

| Thay đổi | Ví dụ |
|---|---|
| **Chỗ / nền** | phòng ngủ, lớp học, hành lang |
| **Ánh sáng** | đèn trần, cạnh cửa sổ, tối hơn bình thường |
| **Tay** | tay phải, tay trái (mỗi tay một video riêng) |
| **Camera** | webcam laptop, điện thoại (camera trước hoặc sau đều được) |

**Mục tiêu tối thiểu:** mỗi cử chỉ **≥ 10 video**, của **≥ 3 người**. Ít hơn 5 video một lớp thì
notebook không chia đủ 5 fold.

**Lớp `none` quan trọng không kém** — đó là những gì KHÔNG phải cử chỉ: tay thả lỏng, tay đang
chuyển từ cử chỉ này sang cử chỉ khác, tay đang hạ xuống, tay nửa nắm nửa mở, gãi đầu, cầm điện
thoại. Quay riêng các video này cho thư mục `none`.

**Tránh:**
- đổi cử chỉ giữa chừng trong một video (script lấy nhãn theo thư mục cho cả video);
- hai bàn tay cùng trong khung;
- tay bị che một phần, nhoè vì đưa quá nhanh, hoặc ra khỏi khung.

Script tự bỏ 0.7 giây đầu và cuối video (lúc đang đưa tay vào / rút ra), nên không cần cắt.

## 3. Bỏ video vào thư mục

Chạy lần đầu để script tự tạo thư mục:

```powershell
cd D:\IoT_Gesture_sequence_door_lock
.conda\python.exe scripts\trich_video.py
```

```
data_video\
    fist\  palm\  victory\  thumb_up\  point_up\  ok\  none\
```

Chép video vào đúng thư mục. Tên file tuỳ ý, nên ghi người và chỗ cho dễ nhớ:
`palm\quang_cuaso_trai.mp4`. Định dạng: `.mp4`, `.mov`, `.avi`, `.mkv`, `.m4v`, `.webm`.

> `data_video\` đã có trong `.gitignore`: video nặng và có mặt người, **không** đưa lên GitHub.

## 4. Chạy thử — chưa ghi gì

```powershell
.conda\python.exe scripts\trich_video.py --chay-thu
```

Bảng in ra cho từng video:

| Cột | Ý nghĩa |
|---|---|
| `mau` | số mẫu lấy được (5 khung/giây sau khi bỏ đầu cuối) |
| `mat tay` | số khung MediaPipe không thấy tay — nhiều quá thì tay nhỏ quá hoặc tối quá |
| `model dong y` | model hiện tại đoán trúng nhãn bao nhiêu % |

**`<- NGHI SAI NHAN`** khi model đoán trúng dưới 50%: hầu hết là bỏ nhầm thư mục. Mở ảnh trong
`data_video\_xem_truoc\` (12 khung mẫu của mỗi video, có vẽ khung xương bàn tay) để kiểm tra.
Nếu nhãn đúng mà model vẫn đoán sai, **đó chính là video có giá trị** — giữ lại.

## 5. Ghi thật rồi train lại

```powershell
.conda\python.exe scripts\trich_video.py
```

- Script **sao lưu** `keypoint.csv` và `keypoint_meta.csv` trước khi ghi
  (đuôi `_truoc_video_<ngày giờ>`). Muốn quay lại thì chép đè file sao lưu.
- Video đã trích được nhớ trong `data_video\_da_trich.csv` → quay thêm video rồi chạy lại,
  chỉ video mới được thêm.
- Mỗi video là một nhóm (`burst_id = vid_<nhãn>_<tên file>`) → notebook chia train/validation
  theo video, mẫu của cùng một video không bao giờ nằm ở cả hai phía.

Sau đó mở `vision\train_classifier.ipynb` → **Run All**, rồi
`.conda\python.exe vision\eval_external.py` để đo lại trên HaGRID.

## 6. Tuỳ chọn

| Tham số | Mặc định | Khi nào đổi |
|---|---|---|
| `--buoc-giay 0.2` | 5 khung/giây | video ngắn quá thì giảm xuống 0.1 |
| `--cat-dau 0.7 --cat-cuoi 0.7` | bỏ 0.7 giây hai đầu | nếu bắt đầu quay khi đã giữ sẵn cử chỉ thì đặt 0 |
| `--toi-da 150` | tối đa 150 mẫu/video | để video dài không lấn át |
| `--tay phai` / `--tay trai` | tự đoán theo đa số khung | khi script báo MediaPipe đoán ngược tay nhiều |
| `--thu-muc <đường dẫn>` | `data_video\` | để video ở ổ khác |

## 7. Công dụng của Scripts

1. Lấy 1 khung mỗi 0.2 giây, bỏ 0.7 giây đầu và cuối.
2. Lật ngang khung giống `gesture_lock.py`, chạy MediaPipe HandLandmarker, bỏ khung không thấy tay.
3. **Đổi tỉ lệ khung hình.** Video điện thoại là 16:9 hoặc dọc 9:16, camera lúc chạy thật là
   640×480 (4:3). Toạ độ MediaPipe chuẩn hoá theo từng trục nên cùng một bàn tay sẽ bị "méo" khác
   nhau. Script đổi về đúng quy ước của camera 640×480 trước khi tính đặc trưng (đã có test:
   cùng một bàn tay trong khung 640×480, 1280×720, 1920×1080, 1080×1920 cho cùng một vector).
4. **Thống nhất tay trái/phải theo cả video.** MediaPipe đôi khi đoán nhầm tay ở vài khung lẻ,
   làm mẫu đó bị lật ngược; mỗi video chỉ dùng một tay nên lấy nhãn tay chiếm đa số.
5. Đưa qua đúng `preprocess_landmarks()` như lúc chạy thật → 42 số, ghi vào `keypoint.csv`.
