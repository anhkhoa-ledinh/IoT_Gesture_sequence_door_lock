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

 Song song, moi mau ghi them MOT dong vao vision/model/keypoint_meta.csv:
   session_id = thoi diem bat dau lan chay nay, vd s20261024_153012
   burst_id   = <session_id>_bNNN, moi lan bam R hoac SPACE la mot burst moi
 Dong thu i cua hai file luon ung voi nhau. Notebook dung burst_id de chia
 train/val sao cho 30 mau cua cung mot lan bam R khong nam o ca hai phia.

 LUU Y: file KHONG BAO GIO bi ghi de. Chay lai nhieu lan de bo sung du lieu.
 Neu hai file khong khop so dong, script tu choi chay de khong lech them.
============================================================================
"""

from __future__ import annotations

import csv
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
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


META_HEADER = ["session_id", "burst_id"]


def count_data_rows(path: Path, has_header: bool) -> int:
    """So dong du lieu trong file CSV (bo dong trong, bo dong tieu de neu co)."""
    if not path.exists():
        return 0
    with open(path, "r", newline="", encoding="utf-8") as f:
        n = sum(1 for row in csv.reader(f) if row)
    return max(0, n - 1) if has_header else n


def check_meta_aligned(csv_path: Path, meta_path: Path) -> int:
    """Bao loi neu keypoint.csv va keypoint_meta.csv khong khop tung dong.

    Lech mot dong la toan bo burst_id phia sau gan nham mau, va notebook se chia
    train/val sai ma khong co dau hieu gi. Vi vay dung han thay vi ghi tiep.
    Tra ve so dong du lieu hien co.
    """
    n_data = count_data_rows(csv_path, has_header=False)
    n_meta = count_data_rows(meta_path, has_header=True)
    if n_data != n_meta:
        raise RuntimeError(
            f"{csv_path.name} co {n_data} dong nhung {meta_path.name} co {n_meta} dong.\n"
            "Hai file phai khop tung dong. Khong thu tiep de tranh lech them —\n"
            "kiem tra lai hai file (ban sao luu: vision/model/keypoint_backup_*.csv)."
        )
    return n_data


def append_sample(csv_path: Path, meta_path: Path, class_id: int,
                  features: np.ndarray, session_id: str, burst_id: str) -> None:
    """Ghi them 1 mau vao cuoi keypoint.csv VA 1 dong vao keypoint_meta.csv.

    Hai file luon tang cung nhau dung mot dong. Mo che do 'a' nen khong bao gio
    ghi de. keypoint.csv giu nguyen 43 cot nhu cu.
    """
    if features.shape != (FEATURE_DIM,):
        raise ValueError(f"Vector dac trung phai co {FEATURE_DIM} chieu, "
                         f"nhan duoc {features.shape}")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    meta_moi = not meta_path.exists() or meta_path.stat().st_size == 0
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([class_id] + [f"{v:.6f}" for v in features])
    with open(meta_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if meta_moi:
            w.writerow(META_HEADER)
        w.writerow([session_id, burst_id])


class CollectSession:
    """Mot lan chay collect_data.py: session_id va cac burst da ghi trong phien.

    Thuan logic, khong dung camera — test duoc bang du lieu gia.
    """

    def __init__(self, started_at: datetime | None = None) -> None:
        started_at = started_at or datetime.now()
        self.session_id = started_at.strftime("s%Y%m%d_%H%M%S")
        self._next = 0
        self._bursts_by_class: dict[int, set[str]] = defaultdict(set)

    def new_burst(self) -> str:
        """Cap mot burst_id moi. Goi moi lan bam R hoac SPACE."""
        burst_id = f"{self.session_id}_b{self._next:03d}"
        self._next += 1
        return burst_id

    def mark_written(self, class_id: int, burst_id: str) -> None:
        """Ghi nhan burst da co it nhat 1 mau. Burst bam R ma mat tay ngay thi khong tinh."""
        self._bursts_by_class[class_id].add(burst_id)

    def burst_count(self, class_id: int) -> int:
        return len(self._bursts_by_class[class_id])


# ============================================================================
#  2. VE GIAO DIEN
# ============================================================================

def draw_hud(frame, id_to_label, counts, current_id, burst_left, has_hand,
             session, burst_target):
    """Ve bang thong tin len khung hinh: lop dang chon, so mau moi lop, phim tat.

    Cot ben trai hien them 'phien N/muc tieu': so burst cua lop do da ghi TRONG
    LAN CHAY NAY. Lop nao du muc tieu thi chuyen xanh — nhin la biet lop nao con thieu.
    """
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

    # Cot ben trai: tong so mau tung lop + so burst trong phien nay.
    y = 90
    for cid in sorted(id_to_label):
        n_burst = session.burst_count(cid)
        if cid == current_id:
            color = (0, 255, 255)                     # vang: lop dang chon
        elif n_burst >= burst_target:
            color = (0, 200, 0)                       # xanh: du muc tieu phien nay
        else:
            color = (200, 200, 200)
        cv2.putText(frame, f"{cid} {id_to_label[cid]:<9} {counts[cid]:>4}"
                           f"  phien {n_burst}/{burst_target}",
                    (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
        y += 22

    cv2.putText(frame, "0-6 chon lop | SPACE ghi 1 mau | R ghi 30 mau | Q thoat",
                (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


def print_summary(id_to_label, counts, csv_path, session, burst_target):
    """In bang dem so mau moi lop va so burst trong phien khi thoat."""
    print()
    print("=" * 52)
    print("TONG KET SO MAU TRONG", csv_path)
    print("Phien:", session.session_id)
    print("=" * 52)
    print(f"{'id':<4}{'lop':<12}{'so mau':>8}{'burst phien nay':>18}")
    print("-" * 52)
    total = 0
    for cid in sorted(id_to_label):
        n = counts[cid]
        total += n
        canh_bao = "  <-- con it" if n < 250 else ""
        n_burst = session.burst_count(cid)
        thieu = "" if n_burst >= burst_target else " (thieu)"
        print(f"{cid:<4}{id_to_label[cid]:<12}{n:>8}{n_burst:>11}/{burst_target}{thieu}{canh_bao}")
    print("-" * 52)
    print(f"{'':<16}{total:>8}  tong cong")
    print("=" * 52)
    print("Muc tieu: 250-300 mau moi lop, KE CA lop 'none'.")
    print(f"Moi phien: moi lop it nhat {burst_target} lan bam R (collect.session_burst_target).")


# ============================================================================
#  3. VONG LAP CHINH
# ============================================================================

def main() -> int:
    cfg = load_config()
    id_to_label, _ = gesture_tables(cfg)
    csv_path = resolve_path(cfg["model"]["keypoint_csv"])
    meta_path = resolve_path(cfg["model"]["keypoint_meta_csv"])

    # Kiem tra hai file khop tung dong TRUOC khi mo webcam.
    try:
        check_meta_aligned(csv_path, meta_path)
    except RuntimeError as e:
        print("LOI:", e)
        return 1
    counts = count_existing_samples(csv_path)

    burst_total = cfg["collect"]["burst_samples"]      # 30
    burst_step = cfg["collect"]["burst_frame_step"]    # ghi cach nhau 2 khung
    burst_target = cfg["collect"]["session_burst_target"]

    # Moi lan chay la mot phien moi -> session_id moi.
    session = CollectSession()
    burst_r_id = None                                  # burst_id cua lan bam R dang ghi
    print(f"Phien thu: {session.session_id}  (ghi meta vao {meta_path.name})")

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
                    append_sample(csv_path, meta_path, current_id, features,
                                  session.session_id, burst_r_id)
                    session.mark_written(current_id, burst_r_id)
                    counts[current_id] += 1
                    burst_left -= 1
                elif features is None:
                    # Mat tay giua chung thi dung han, tranh ghi rac.
                    print("Mat tay, huy che do ghi lien tuc.")
                    burst_left = 0

            draw_hud(frame, id_to_label, counts, current_id, burst_left, has_hand,
                     session, burst_target)
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
                    # Moi lan bam SPACE la mot burst rieng (1 mau). Khong dung
                    # burst_r_id de mau le khong bi gop vao burst R dang ghi do.
                    burst_space_id = session.new_burst()
                    append_sample(csv_path, meta_path, current_id, features,
                                  session.session_id, burst_space_id)
                    session.mark_written(current_id, burst_space_id)
                    counts[current_id] += 1
                    print(f"ghi 1 mau lop {current_id} "
                          f"({id_to_label[current_id]}) -> tong {counts[current_id]}")
            elif key in (ord("r"), ord("R")):             # ghi lien tuc
                burst_left = burst_total
                burst_r_id = session.new_burst()          # moi lan bam R = burst moi
                print(f"ghi lien tuc {burst_total} mau cho lop {current_id} "
                      f"({id_to_label[current_id]}) -> {burst_r_id}")

    cap.release()
    cv2.destroyAllWindows()
    print_summary(id_to_label, counts, csv_path, session, burst_target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
