# Kết quả cải tiến huấn luyện (31/10/2026)

Tài liệu này ghi lại **từng thay đổi** đã thử trên bộ phân loại cử chỉ, con số trước/sau,
và lý do giữ hay bỏ. Mọi con số đo theo **cùng một cách**: kiểm định chéo 5 fold
`StratifiedGroupKFold` chia theo `burst_id`, chỉ chấm trên burst **tự thu** mà model chưa
thấy. Dữ liệu ngoài (nếu dùng) chỉ được thêm vào **phần train** của mỗi fold.

Hai thước đo chính:

- **Tự thu (OOF)** — độ chính xác out-of-fold trên 2 504 mẫu webcam của nhóm.
- **HaGRID 6 cử chỉ** — model train trên toàn bộ dữ liệu được chấm trên 1 800 ảnh HaGRID
  (bỏ lớp `none` vì khác định nghĩa). HaGRID **không bao giờ** được dùng để train, nên đây là
  phép đo "có nhận được tay người lạ không".

---

## 1. Kết luận ngắn

| | Mốc gốc (mạng 26/09) | **Cấu hình chọn** |
|---|---|---|
| Tự thu, trung bình 3 lần train (seed khác nhau) | 62.0% ± 1.2 | **78.9% ± 1.4** |
| Tự thu, bản notebook chính thức (`eval_metrics.json`) | — | **76.6%** (trung bình fold 76.5% ± 4.3) |
| HaGRID 6 cử chỉ, trung bình 3 lần train | 64.3% ± 3.6 | **86.5% ± 4.0** |
| HaGRID bản notebook chính thức (`eval_external.py`) | 62.2% (model 26/09) | **84.7%** (1 525/1 800) |
| HaGRID cả 7 lớp — con số thô | 53.8% (model 26/09) | **72.7%** |
| Trung vị độ tin cậy trên các dự đoán đúng | 0.55 | **0.93** |
| Ngưỡng `min_confidence` dùng được | phải hạ tay xuống 0.45 | **0.80**, chọn có căn cứ (mục 4) |

Cấu hình chọn: **mạng 64-32 + dữ liệu GitHub (trọng số 0.5) + trọng số lớp `none` ×2**, đầu
vào giữ nguyên 42 chiều. Hai thứ đã thử và **bỏ**: đặc trưng góc ngón tay, augmentation.

**Vì sao báo "trung bình 3 lần train":** cùng một cấu hình, chỉ đổi seed ngẫu nhiên, độ chính
xác tự thu dao động 76.6–80.4%. Chênh lệch giữa hai cấu hình nhỏ hơn khoảng đó thì **không**
kết luận được gì. Chỉ các bước tăng lớn (mạng mới: +11 điểm; dữ liệu GitHub: +6 điểm tự thu,
+15 điểm HaGRID) là chắc chắn.

---

## 2. Từng giai đoạn (seed 42)

| GĐ | Thay đổi | Tự thu OOF | macro-F1 | `none` recall | HaGRID 6 cử chỉ | Độ tin cậy trung vị | Giữ? |
|---|---|---|---|---|---|---|---|
| K0 | **Mốc gốc** — mạng cũ `Dropout(0.2)→20→Dropout(0.4)→10`, chỉ dữ liệu tự thu | 61.0% | 59.7% | 50% | 68.1% | 0.55 | — |
| K1 | Mạng mới `64→Dropout(0.3)→32→Dropout(0.2)`, bỏ dropout đầu vào | 74.3% | 73.1% | 74% | 73.2% | 0.88 | ✅ |
| K2 | + 20 đặc trưng góc ngón tay (chỉ dữ liệu tự thu) | 72.8% | 71.8% | 59% | 63.3% | 0.86 | ❌ |
| K3 | + dữ liệu GitHub, trọng số 0.5 (vẫn có góc) | 79.2% | 78.3% | 58% | 71.2% | 0.93 | ✅ GitHub |
| K4 | + trọng số `none` ×2 (vẫn có góc) | 78.3% | 77.9% | 68% | 78.1% | 0.90 | ✅ none×2 |
| K5 | + augmentation (vẫn có góc) | 80.4% | 79.9% | 70% | 75.4% | 0.93 | ? |
| K6 | **Bỏ góc**, giữ GitHub + none×2 + augmentation | 80.2% | 79.8% | 72% | **91.3%** | 0.93 | ✅ bỏ góc |
| K7 | Như K5, GitHub trọng số 1.0 | 80.9% | 80.5% | 70% | 76.7% | 0.94 | — |
| K8 | Như K6, GitHub trọng số 1.0 | 80.6% | 80.1% | 70% | 90.1% | 0.95 | — |
| **K9** | **Như K6, bỏ augmentation** | **80.4%** | **80.0%** | **76%** | **90.0%** | **0.94** | ✅ **chọn** |

### Đọc bảng

- **Mạng mới (K0 → K1): +13 điểm, độ tin cậy 0.55 → 0.88.** Đây là lời giải thích cho hiện
  tượng lúc demo ngày 24/10: độ tin cậy chỉ 0.45–0.54, không cử chỉ nào qua được ngưỡng 0.70.
  Nguyên nhân là mạng cũ quá hẹp (`Dense(10)`) và có dropout ngay ở đầu vào (tắt ngẫu nhiên
  từng toạ độ — giống che mất đầu ngón tay lúc học).
- **Dữ liệu GitHub (K1 → K3/K9): +6 điểm tự thu, HaGRID 73 → 90%.** Dữ liệu do người khác
  thu giúp model nhận tay người lạ — đúng điểm yếu lớn nhất của dữ liệu một người, một phiên.
- **Trọng số `none` ×2:** dữ liệu GitHub không có lớp `none`, nên khi thêm vào thì `none`
  recall tụt (74% → 58% ở K3). Nhân đôi trọng số mẫu `none` kéo lại được (58% → 68–76%).
- **Đặc trưng góc ngón tay — bỏ.** Trên dữ liệu tự thu không tốt hơn (K2 72.8% < K1 74.3%;
  3 seed: 78.3% so với 78.9%), còn trên HaGRID **kém hẳn**: 72.6% ± 5.1 so với 86.5% ± 4.0
  (3 seed mỗi bên). Giả thuyết: ảnh HaGRID được cắt quanh bàn tay rồi mới chạy MediaPipe, tỉ
  lệ khung khác hẳn camera 640×480, nên góc tính trên toạ độ chuẩn hoá bị méo theo cách khác;
  model dựa vào góc thì "lệch" khi gặp nguồn ảnh khác. Chưa kiểm chứng giả thuyết này.
- **Augmentation (xoay ±15°, co giãn, nhiễu) — bỏ.** K6 (có) 80.2% so với K9 (không) 80.4%,
  `none` 72% so với 76%. Khi đã có 15 nghìn mẫu GitHub thì augmentation không thêm gì.
- **Trọng số GitHub 1.0 so với 0.5** — không khác biệt đáng kể (K8 ≈ K6). Giữ 0.5 để dữ liệu
  webcam của chính nhóm không bị lấn át.

### Lặp lại 3 seed

| Cấu hình | Seed 42 | Seed 1 | Seed 2 | Trung bình ± độ lệch | HaGRID 6 cử chỉ (TB) |
|---|---|---|---|---|---|
| Mạng cũ, chỉ tự thu | 61.0% | 61.8% | 63.3% | 62.0% ± 1.2 | 64.3% |
| Mạng mới, chỉ tự thu | 74.3% | 73.1% | 71.8% | 73.1% ± 1.2 | 71.1% |
| **Mạng mới + GitHub + none×2** | 80.4% | 78.9% | 77.6% | **78.9% ± 1.4** | **86.5%** |
| Như trên + góc ngón tay | 78.3% | 77.3% | 79.4% | 78.3% ± 1.0 | 72.6% |

Bản notebook chính thức (cùng cấu hình, seed 42 nhưng thứ tự dữ liệu GitHub khác) cho 76.6% —
nằm trong khoảng dao động trên. Con số đưa vào báo cáo là của notebook (`eval_metrics.json`).

---

## 3. Từng lớp — bản notebook chính thức

| Lớp | Mốc gốc K0 (OOF) | **Model mới (OOF)** | HaGRID — model 26/09 | **HaGRID — model mới** |
|---|---|---|---|---|
| `fist` | 48% | **86.0%** | 94.7% | **95.0%** |
| `palm` | 77% | **89.9%** | 98.0% | **99.7%** |
| `victory` | 72% | 58.1% | 51.0% | **94.3%** |
| `thumb_up` | 52% | **83.3%** | 7.7% | **70.0%** |
| `point_up` | 40% | **68.3%** | 71.0% | 55.3% |
| `ok` | 77% | **78.9%** | 51.0% | **94.0%** |
| `none` | 50% | **70.0%** | N/A | N/A (khác định nghĩa) |
| **Tổng thể** | 61.0% | **76.6%** | 53.8% (7 lớp) | **72.7%** (7 lớp) / **84.7%** (6 cử chỉ) |

Các cặp còn nhầm trên 10% (ma trận out-of-fold, `docs/confusion_matrix.png`):
`victory → point_up` 19.3%, `point_up → victory` 15.7%, `thumb_up → fist` 14.9%,
`victory → none` 14.3%, `point_up → none` 12.0%.

**`victory` là lớp kỳ lạ:** trên tay người lạ (HaGRID) đạt 94.3%, nhưng trên chính dữ liệu tự
thu chỉ 58.1%. Phép 1-NN bỏ burst ngày 23/10 cũng cho `victory` 52.4% — tức là các burst
`victory` tự thu **không giống nhau**: có lần hai ngón khép gần như `point_up`. Đây là vấn đề
dữ liệu tự thu, không phải của model.

---

## 4. Chọn ngưỡng `min_confidence` bằng giả lập máy trạng thái

`gesture_lock.py` chỉ chấp nhận một cử chỉ khi có **15 khung liên tiếp** cùng nhãn và vượt
ngưỡng. Burst ghi 30 mẫu cách nhau 2 khung, nên 15 khung ≈ 8 mẫu liên tiếp. Notebook Bước 7b
chạy đúng luật đó trên dự đoán out-of-fold của 76 burst cử chỉ và 10 burst `none`:

| Ngưỡng | Chấp nhận đúng | Chấp nhận **SAI** | Chưa chấp nhận (giữ tay lâu hơn) | `none` bị đọc nhầm |
|---|---|---|---|---|
| 0.45 | 63 | 6 | 7 | 2 / 10 |
| 0.60 | 62 | 5 | 9 | 2 / 10 |
| 0.70 | 55 | 5 | 16 | 2 / 10 |
| **0.80** | **52** | **2** | 22 | 1 / 10 |
| 0.90 | 41 | 2 | 33 | 1 / 10 |

Luật chọn: ngưỡng **nhỏ nhất** mà burst bị chấp nhận **sai ≤ 3%** → **0.80**. Khi đã chấp nhận
thì đúng 52/54 = **96.3%**. "Chưa chấp nhận" không gây sai mã — burst chỉ dài 2 giây, ngoài đời
người dùng giữ tay lâu hơn. Nếu thấy phải giữ tay quá lâu, hạ xuống 0.70 (đổi lại: sai 5/76).

So sánh: mạng cũ (K0, train lại trên cùng dữ liệu) ở ngưỡng 0.45 — giá trị đang dùng trước
31/10 — chỉ có 37/76 burst được chấp nhận đúng, 9 burst bị chấp nhận **sai**; ở ngưỡng 0.70
theo thiết kế ban đầu thì chỉ 19/76 burst được chấp nhận.

---

## 5. Chọn lại mật mã

Theo từng lớp, ở ngưỡng 0.80 (giả lập trên model K9, cùng cấu hình):

| Cử chỉ | Burst chấp nhận đúng | Sai | Chưa nhận |
|---|---|---|---|
| `palm` | 13 / 14 | 0 | 1 |
| `ok` | 12 / 13 | 0 | 1 |
| `fist` | 9 / 12 | 0 | 3 |
| `thumb_up` | 9 / 13 | 2 | 2 |
| `victory` | 7 / 14 | 0 | 7 |
| `point_up` | 5 / 10 | 0 | 5 |

Mật mã đổi từ `palm → victory → fist` (`7CE13A`) sang **`palm → ok → fist` (`7C4D3A`)**:
`victory` chỉ được nhận trong 7/14 burst, `ok` được 12/13; không có cử chỉ nào trong mã mới bị
chấp nhận sai. Không dùng `thumb_up` vì `thumb_up → fist` 14.9%. Trên HaGRID cả `ok` lẫn
`victory` đều trên 94% — lý do đổi là độ dùng được trên **tay người dùng thật**.

---

## 6. Dữ liệu GitHub dùng để train

| Nguồn | Giấy phép | Lớp lấy | Số mẫu |
|---|---|---|---|
| [thatsabhishek/hand-gesture-recognition-using-mediapipe](https://github.com/thatsabhishek/hand-gesture-recognition-using-mediapipe) (gồm dữ liệu gốc của Kazuhito00 + OK của kinivi) | Apache-2.0 | Open, Close, Pointer, OK, Peace, Thumbs Up | 5 275 |
| [jaeeun/hand-gesture-recognition-using-mediapipe](https://github.com/jaeeun/hand-gesture-recognition-using-mediapipe) | Apache-2.0 | Open, Close, Pointer, OK, V, Thumb | 10 345 |
| **Tổng** (đã kiểm: không dòng nào trùng giữa hai bộ) | | | **15 620** |

Theo lớp: fist 3 555 · palm 3 350 · victory 1 654 · thumb_up 1 736 · point_up 3 307 · ok 2 018.
Không có lớp `none`.

Hai bộ dùng **cùng pipeline** với dự án (MediaPipe 21 điểm → dời gốc về cổ tay → chia
max_abs). Khác biệt duy nhất: các repo đó lấy toạ độ **pixel**, dự án lấy toạ độ **chuẩn hoá
0..1** của camera 640×480 (trục x bị nén 0.75 lần). `scripts/chuyen_du_lieu_github.py` nhân x
với 480/640 rồi chuẩn hoá lại — phép đổi chính xác vì pixel là hình vuông. Đã vẽ khung xương
ngẫu nhiên mỗi lớp của từng nguồn để kiểm nhãn bằng mắt trước khi dùng.

Lưu ý: `Pointer` của các bộ này chỉ ngón trỏ theo **mọi hướng**, không chỉ hướng lên như
`point_up` của dự án — model vì thế dễ dãi hơn với `point_up` nghiêng.

---

## 7. Cách tái lập

```powershell
cd D:\IoT_Gesture_sequence_door_lock
.conda\python.exe scripts\chuyen_du_lieu_github.py      # chỉ cần nếu muốn tạo lại keypoint_github.csv
.conda\python.exe -m jupyter lab                         # mở vision\train_classifier.ipynb -> Run All
.conda\python.exe vision\eval_external.py                # đo lại trên HaGRID
```

Các phép thử ở mục 2 chạy bằng script riêng ngoài repo (cùng quy trình với notebook: cùng
5 fold, cùng EarlyStopping `patience=20`, cùng trọng số mẫu). Số notebook có thể lệch vài
điểm so với bảng mục 2 vì dao động giữa các lần train — xem mục "Lặp lại 3 seed".
