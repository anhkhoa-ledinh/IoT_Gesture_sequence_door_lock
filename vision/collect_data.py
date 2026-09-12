"""
============================================================================
 collect_data.py — Thu du lieu huan luyen cho bo phan loai cu chi
----------------------------------------------------------------------------
 Chay:
   D:\\IoT_Gesture_sequence_door_lock\\.conda\\python.exe vision\\collect_data.py

 Phim:
   0..6    chon lop can thu (theo class_id trong config.json)
   SPACE   ghi 1 mau
   R       ghi lien tuc 30 mau, cach nhau 2 khung
   Q       thoat

 Du lieu ghi APPEND vao vision/model/keypoint.csv:
   cot 1  = class_id
   cot 2..43 = vector dac trung 42 chieu tu preprocess_landmarks()

 LUU Y: file KHONG BAO GIO bi ghi de. Chay lai nhieu lan de bo sung du lieu.
============================================================================
"""

from __future__ import annotations

import csv
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision

from common import (
    FEATURE_DIM,
    draw_landmarks,
    ensure_hand_landmarker,
    gesture_tables,
    load_config,
    preprocess_landmarks,
    resolve_path,
)


# ============================================================================
#  1. DOC / GHI FILE CSV
# ============================================================================

def count_existing_samples(csv_path: Path) -> Counter:
    """Dem so mau da co san moi lop, de hien thi tiep chu khong dem lai tu 0."""
    counts = Counter()
    if not csv_path.exists():
        return counts

    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row:
                continue
            try:
                counts[int(row[0])] += 1
            except ValueError:
                continue  # bo qua dong hong
    return counts


def append_sample(csv_path: Path, class_id: int, features: np.ndarray) -> None:
    """Ghi them 1 mau vao cuoi file. Mo che do 'a' nen khong bao gio ghi de."""
    if features.shape != (FEATURE_DIM,):
        raise ValueError(f"Vector dac trung phai co {FEATURE_DIM} chieu, "
                         f"nhan duoc {features.shape}")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([class_id] + [f"{v:.6f}" for v in features])


# ============================================================================
#  2. VE GIAO DIEN
# ============================================================================

def draw_hud(frame, id_to_label, counts, current_id, burst_left, has_hand):
    """Ve bang thong tin len khung hinh: lop dang chon, so mau moi lop, phim tat."""
    h, w = frame.shape[:2]

    # Nen mo phia tren cho de doc chu.
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 60), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    label = id_to_label.get(current_id, "?")
    cv2.putText(frame, f"[{current_id}] {label.upper()}", (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
    cv2.putText(frame, f"da thu: {counts[current_id]}", (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    # Trang thai ban tay.
    if has_hand:
        cv2.putText(frame, "CO TAY", (w - 150, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    else:
        cv2.putText(frame, "KHONG THAY TAY", (w - 250, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # Dang ghi lien tuc.
    if burst_left > 0:
        cv2.putText(frame, f"DANG GHI... con {burst_left}", (w - 250, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

    # Cot ben trai: so mau tung lop.
    y = 90
    for cid in sorted(id_to_label):
        color = (0, 255, 255) if cid == current_id else (200, 200, 200)
        cv2.putText(frame, f"{cid} {id_to_label[cid]:<9} {counts[cid]:>4}",
                    (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
        y += 22

    cv2.putText(frame, "0-6 chon lop | SPACE ghi 1 mau | R ghi 30 mau | Q thoat",
                (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


def print_summary(id_to_label, counts, csv_path):
    """In bang dem so mau moi lop khi thoat."""
    print()
    print("=" * 46)
    print("TONG KET SO MAU TRONG", csv_path)
    print("=" * 46)
    print(f"{'id':<4}{'lop':<12}{'so mau':>8}")
    print("-" * 46)
    total = 0
    for cid in sorted(id_to_label):
        n = counts[cid]
        total += n
        canh_bao = "  <-- con it" if n < 250 else ""
        print(f"{cid:<4}{id_to_label[cid]:<12}{n:>8}{canh_bao}")
    print("-" * 46)
    print(f"{'':<16}{total:>8}  tong cong")
    print("=" * 46)
    print("Muc tieu: 250-300 mau moi lop, KE CA lop 'none'.")


# ============================================================================
#  3. VONG LAP CHINH
# ============================================================================

def main() -> int:
    cfg = load_config()
    id_to_label, _ = gesture_tables(cfg)
    csv_path = resolve_path(cfg["model"]["keypoint_csv"])
    counts = count_existing_samples(csv_path)

    burst_total = cfg["collect"]["burst_samples"]      # 30
    burst_step = cfg["collect"]["burst_frame_step"]    # ghi cach nhau 2 khung

    model_path = ensure_hand_landmarker(cfg)

    # MediaPipe Tasks API — RunningMode.VIDEO vi ta xu ly luong khung lien tuc.
    # KHONG dung mp.solutions.hands (API cu, se xung dot voi Tasks API).
    options = mp_vision.HandLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=mp_vision.RunningMode.VIDEO,
        num_hands=cfg["model"]["num_hands"],
    )

    cam = cfg["camera"]
    cap = cv2.VideoCapture(cam["camera_index"], cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam["frame_width"])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam["frame_height"])
    if not cap.isOpened():
        print(f"LOI: khong mo duoc webcam index {cam['camera_index']}.")
        print("Sua camera.camera_index trong vision/config.json roi chay lai.")
        return 1

    current_id = 0
    burst_left = 0
    frame_idx = 0
    t0 = time.monotonic()
    last_ts = -1

    print("Da mo webcam. Bam Q trong cua so video de thoat.")

    with mp_vision.HandLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("LOI: mat tin hieu webcam.")
                break

            # Lat ngang de thanh anh guong — nguoi dung thay tay minh dung chieu.
            # MediaPipe gia dinh anh dau vao la anh guong khi bao Left/Right,
            # nen lat o day thi nhan handedness dung. collect_data.py va
            # gesture_lock.py PHAI lam giong nhau o buoc nay.
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            # RunningMode.VIDEO doi moc thoi gian tang dan tuyet doi.
            ts = int((time.monotonic() - t0) * 1000)
            if ts <= last_ts:
                ts = last_ts + 1
            last_ts = ts

            result = landmarker.detect_for_video(mp_image, ts)
            has_hand = bool(result.hand_landmarks)

            features = None
            if has_hand:
                lms = result.hand_landmarks[0]
                handed = result.handedness[0][0].category_name
                draw_landmarks(frame, lms)
                features = preprocess_landmarks(lms, handed)

            # --- Ghi lien tuc (phim R): cach nhau burst_step khung ---
            if burst_left > 0:
                if features is not None and frame_idx % burst_step == 0:
                    append_sample(csv_path, current_id, features)
                    counts[current_id] += 1
                    burst_left -= 1
                elif features is None:
                    # Mat tay giua chung thi dung han, tranh ghi rac.
                    print("Mat tay, huy che do ghi lien tuc.")
                    burst_left = 0

            draw_hud(frame, id_to_label, counts, current_id, burst_left, has_hand)
            cv2.imshow("Thu du lieu cu chi - Q de thoat", frame)
            frame_idx += 1

            key = cv2.waitKey(1) & 0xFF
            if key == 255:
                continue

            if key in (ord("q"), ord("Q"), 27):          # Q hoac ESC
                break
            elif ord("0") <= key <= ord("6"):            # chon lop
                current_id = key - ord("0")
                burst_left = 0                            # doi lop thi huy burst
                print(f"-> chon lop {current_id} ({id_to_label[current_id]})")
            elif key == 32:                               # SPACE: ghi 1 mau
                if features is None:
                    print("Khong thay tay, khong ghi.")
                else:
                    append_sample(csv_path, current_id, features)
                    counts[current_id] += 1
                    print(f"ghi 1 mau lop {current_id} "
                          f"({id_to_label[current_id]}) -> tong {counts[current_id]}")
            elif key in (ord("r"), ord("R")):             # ghi lien tuc
                burst_left = burst_total
                print(f"ghi lien tuc {burst_total} mau cho lop {current_id} "
                      f"({id_to_label[current_id]})")

    cap.release()
    cv2.destroyAllWindows()
    print_summary(id_to_label, counts, csv_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
